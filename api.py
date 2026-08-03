import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app import billing, crm, jira_channel, kb, orders, ratelimit, store
from app.agents import learn_agent
from app.email_channel import fetch_unread, send_email
from app.graph import auto_tags, graph
from app.orchestrator import graph_auto
from app.router import MODEL_TIER
from app.schemas import UserCreate, UserRead, UserUpdate
from app.state import Ticket, public_messages
from app.users import (
    User,
    auth_backend,
    create_user_table,
    current_user,
    fastapi_users,
    require_admin,
    require_staff,
)

# AGENT_MODE toggle: deterministic (fixed LangGraph pipeline) | autonomous (5 ReAct agents + orchestrator)
AGENT_MODE = os.getenv("AGENT_MODE", "deterministic").lower()
active_graph = graph_auto if AGENT_MODE == "autonomous" else graph

app = FastAPI(title="Support Ticket Triage API")

# comma-separated list, e.g. "https://demo.example.com,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# register/login live in the fastapi-users router, so the limit sits in middleware
_AUTH_LIMITS = {"/auth/register": (5, 3600), "/auth/login": (10, 300)}


@app.middleware("http")
async def _auth_rate_limit(request: Request, call_next):
    limit = _AUTH_LIMITS.get(request.url.path) if request.method == "POST" else None
    if limit:
        try:
            ratelimit.check(f"{request.url.path}:{ratelimit.client_ip(request)}", *limit)
        except HTTPException as e:
            return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    return await call_next(request)


app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])


@app.on_event("startup")
async def _startup():
    store.init_db()  # tables exist when the API BOOTS, not when the module imports (tests need import without a DB)
    await create_user_table()
    stale = store.sweep_stale_processing()
    if stale:
        print(f"startup sweep: {len(stale)} ticket(s) orphaned mid-pipeline by a restart, marked error: {stale}")


@app.get("/config")
def brand_config():
    # the client company's branding; the portal renders this, Enklima stays vendor-side
    return {
        "brand_name": os.getenv("BRAND_NAME", "Support"),
        "brand_tagline": os.getenv("BRAND_TAGLINE", ""),
    }


class TicketIn(BaseModel):
    # caps stop a pasted megabyte from reaching the DB and the paid LLM prompt
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)
    source: str = Field(default="form", max_length=40)
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)


@app.get("/")
def health():
    return {"status": "ok", "mode": AGENT_MODE, "model_tier": MODEL_TIER}


@app.get("/healthz")
def healthz():
    # the honest health check: touches each dependency instead of just answering.
    # /  stays instant for uptime pings; this one is for humans and deploy gates.
    out = {"api": "ok", "mode": AGENT_MODE, "model_tier": MODEL_TIER}
    # up/down only, no exception text: this route is unauthenticated and psycopg
    # errors would leak host/user strings to anyone who asks
    try:
        with store._connect() as conn:
            conn.execute("SELECT 1")
        out["postgres"] = "ok"
    except Exception:
        out["postgres"] = "down"
    try:
        kb.connect().close()
        out["weaviate"] = "ok"
    except Exception:
        out["weaviate"] = "down"
    out["status"] = "ok" if out["postgres"] == "ok" and out["weaviate"] == "ok" else "degraded"
    return out


@app.post("/tickets")
def create_ticket(payload: TicketIn, background: BackgroundTasks, user: User = Depends(current_user)):
    ratelimit.check(f"tickets:{user.email}", 5, 86_400)  # 5/day per account: autonomous mode burns real GPU money per ticket
    ticket_id = f"T-{uuid.uuid4().hex[:8]}"
    if user.role == "customer":
        payload.email = user.email  # identity comes from the account, never the form
        payload.name = payload.name or user.email.split("@")[0]
    store.save_pending(
        ticket_id,
        payload.subject,
        payload.body,
        payload.source,
        payload.name,
        payload.email,
        datetime.now(timezone.utc),
    )
    background.add_task(_process, ticket_id, payload.model_dump())
    return {"ticket_id": ticket_id, "status": "processing"}


ESCALATION_ACK = (
    "Thanks for reaching out. This one needs a specialist's attention, so we've routed it to a "
    "member of our team who will follow up with you directly. We appreciate your patience.\n\n"
    "The Support Team"
)


def _ack_escalation(ticket_id: str) -> None:
    # on escalate, tell the customer a human is coming so they are not left in silence.
    # guard: never post the same acknowledgement twice in a row (safe across reprocess).
    state = store.get(ticket_id)
    agent_msgs = [m for m in (state or {}).get("messages", []) if m["role"] == "agent"]
    if agent_msgs and agent_msgs[-1]["body"] == ESCALATION_ACK:
        return
    store.append_message(ticket_id, "agent", ESCALATION_ACK)


# default matches bench.py's cap; deployed autonomous mode needs more: cold lane
# load (~77s) + a 60-140s five-agent run does not fit inside 180
PIPELINE_TIMEOUT_S = int(os.getenv("PIPELINE_TIMEOUT_S", "180"))

_CANCELLED: set[str] = set()  # resolve marks a ticket doomed; in-flight runs check here before working


def _invoke_guarded(ticket_id: str, initial: dict):
    # run the graph with a hard time cap so one hung ticket can't jam the background queue.
    # two attempts: a timeout is usually a Modal cold start, and the retry hits a warm container.
    for _attempt in (1, 2):
        if ticket_id in _CANCELLED:
            print(f"[pipeline] {ticket_id} cancelled by resolve", flush=True)
            return None
        print(f"[pipeline] {ticket_id} attempt {_attempt} start", flush=True)
        box = {}

        def work():
            try:
                box["final"] = active_graph.invoke(initial, {"recursion_limit": 40})
            except Exception as e:
                box["error"] = str(e)

        th = threading.Thread(target=work, daemon=True)  # daemon: a hung call is abandoned, never blocks exit
        th.start()
        th.join(PIPELINE_TIMEOUT_S)
        if "final" in box:
            print(f"[pipeline] {ticket_id} done on attempt {_attempt}", flush=True)
            return box["final"]
        print(f"[pipeline] {ticket_id} attempt {_attempt} failed: {box.get('error', 'timeout')}", flush=True)
    store.set_status(ticket_id, "error")  # both attempts timed out or crashed: visible, never silent
    return None


_HUMAN_RE = re.compile(r"\b(human|real person|representative|live agent|speak to someone|talk to someone)\b", re.I)


def _wants_human(text: str) -> bool:
    return bool(_HUMAN_RE.search(text or ""))


def _auto_dispatch(ticket_id: str) -> None:
    # auto_send means SEND: the reply leaves immediately, no human click.
    # an explicit "get me a human" always parks at NEEDS REVIEW instead.
    state = store.get(ticket_id)
    if state is None:
        return
    customer_turns = [m["body"] for m in state.get("messages", []) if m["role"] == "customer"]
    if customer_turns and _wants_human(customer_turns[-1]):
        store.set_status(ticket_id, "pending")
        _ack_escalation(ticket_id)
        return
    reply = (state.get("draft") or {}).get("reply", "")
    if (state.get("decision") or {}).get("action") != "auto_send" or not reply.strip():
        return
    store.append_message(ticket_id, "agent", reply)
    dispatch_reply(state, reply, ticket_id)
    store.set_lifecycle(ticket_id, "awaiting_customer")
    store.set_status(ticket_id, "sent")


def _process(ticket_id: str, raw: dict):
    _t0 = time.monotonic()  # shared-layer per-ticket latency capture (feeds the Performance Dashboard)
    final = _invoke_guarded(
        ticket_id,
        {
            "raw_input": {**raw, "ticket_id": ticket_id},
            "messages": [{"role": "customer", "body": raw["body"]}],
            "audit": [],
        },
    )
    if ticket_id in _CANCELLED:
        return
    if final and final.get("ticket") is not None:
        store.save(final)
        store.set_processing_seconds(ticket_id, time.monotonic() - _t0)  # wall-clock of this run
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)
        else:
            _auto_dispatch(ticket_id)
    elif final is not None:
        # graph finished but produced no ticket (e.g. intake rejected): surface it, never strand "processing"
        print(f"[pipeline] {ticket_id} finished without a ticket: {(final.get('decision') or {}).get('reason')}", flush=True)
        store.set_status(ticket_id, "error")


def _reprocess(ticket_id: str, latest: str):
    if _wants_human(latest):
        # the customer asked for a person: no model run, straight to the review queue
        store.set_status(ticket_id, "pending")
        _ack_escalation(ticket_id)
        return
    prior = store.get(ticket_id)  # has the just appended customer turn + original ticket info
    t = prior["ticket"]
    raw = {
        "ticket_id": ticket_id,
        "subject": t["subject"],
        "body": latest,  # newest reply is the live message the pipeline works on
        "source": t.get("source", "form"),
        "name": t.get("customer_name"),
        "email": t.get("customer_email"),
    }
    _t0 = time.monotonic()  # shared-layer per-ticket latency capture (feeds the Performance Dashboard)
    final = _invoke_guarded(ticket_id, {"raw_input": raw, "messages": prior.get("messages", []), "audit": []})
    if ticket_id in _CANCELLED:
        return
    if final and final.get("ticket") is not None:
        store.save(final)
        store.set_processing_seconds(ticket_id, time.monotonic() - _t0)  # wall-clock of this run
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)
        else:
            _auto_dispatch(ticket_id)


def _require_ticket_access(ticket_id: str, user: User) -> dict:
    # staff see everything; a customer only touches tickets born from their email
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if user.role == "customer" and (state["ticket"].get("customer_email") or "").lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="not your ticket")
    return state


def _require_open(state: dict) -> None:
    # a resolved ticket is locked: no approve/reject/edit/note/tag/reply ever again
    if state.get("lifecycle") == "resolved":
        raise HTTPException(status_code=409, detail="ticket is resolved and locked")


@app.get("/my/tickets")
def my_tickets(user: User = Depends(current_user)):
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="customer view")
    return store.list_by_email(user.email)


@app.get("/tickets")
def list_tickets(
    status: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    scope: str = "live",
    sort: str = "newest",
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_staff),
):
    # least-privilege: the live queue is for all staff, raw archive browsing is admin-only.
    # staff reach a customer's past tickets through the history panel on a live ticket instead.
    if scope != "live" and user.role != "admin":
        raise HTTPException(status_code=403, detail="archive browsing is admin only")
    if sort not in store.SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of: {', '.join(store.SORTS)}")
    return store.list_all(status=status, category=category, tag=tag, q=q, scope=scope, limit=limit, offset=offset, sort=sort)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return state


@app.get("/tickets/{ticket_id}/history")
def customer_history(ticket_id: str, user: User = Depends(require_staff)):
    # need-to-know archive access: having this customer's live ticket open unlocks
    # their past tickets, without opening the whole archive to staff
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    email = state["ticket"].get("customer_email") or ""
    if not email:
        return []
    return [r for r in store.list_by_email(email) if r["ticket_id"] != ticket_id]


@app.get("/tickets/{ticket_id}/customer")
def customer_record(ticket_id: str, user: User = Depends(require_staff)):
    # the same need-to-know rule as /history: holding this customer's ticket open
    # unlocks THEIR record, and nothing else. These are the lookups the autonomous
    # agents already make as tools; this puts the same facts on the agent's screen so
    # a human is not worse informed than the pipeline that drafted the reply.
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    email = state["ticket"].get("customer_email") or ""
    if not email:
        return {"profile": None, "orders": [], "charges": []}
    # each store is independent; one being empty or unreachable must not blank the panel
    def _safe(fn, fallback):
        try:
            return fn(email)
        except Exception:
            return fallback

    return {
        "profile": _safe(crm.lookup, None),
        "orders": _safe(orders.orders_for, [])[:5],
        "charges": _safe(billing.charges_for, [])[:5],
    }


def _do_reopen(ticket_id: str) -> str:
    live_id = store.reopen_from_history(ticket_id)
    if live_id is None:
        raise HTTPException(status_code=409, detail="not a reopenable archived ticket")
    _CANCELLED.discard(live_id)  # the resolve marked it doomed; it lives again
    return live_id


@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: str, user: User = Depends(require_staff)):
    return {"ticket_id": _do_reopen(ticket_id), "lifecycle": "open"}


@app.post("/my/tickets/{ticket_id}/reopen")
def customer_reopen(ticket_id: str, user: User = Depends(current_user)):
    # a customer unsatisfied with the answer sends the ticket back to the live queue
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="customer view")
    _require_ticket_access(ticket_id, user)
    return {"ticket_id": _do_reopen(ticket_id), "lifecycle": "open"}


class EditIn(BaseModel):
    reply: str = Field(min_length=1, max_length=20_000)


def dispatch_reply(state: dict, reply: str, ticket_id: str) -> str:
    # send through the channel the ticket arrived on: email -> SMTP, jira -> comment, else in-app
    t = state["ticket"]
    if t.get("source") == "email" and t.get("customer_email"):
        try:
            send_email(t["customer_email"], f"Re: {t['subject']}", reply)
            return "email_sent"
        except Exception as e:
            return f"email_failed: {e}"
    if t.get("source") == "jira":
        issue = store.get_jira_link(ticket_id)
        if issue:
            try:
                jira_channel.post_comment(issue, reply)
                return f"jira_comment:{issue}"
            except Exception as e:
                return f"jira_failed: {e}"
    return "in_app"


@app.post("/tickets/{ticket_id}/approve")
def approve_reply(ticket_id: str, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    reply = (state.get("draft") or {}).get("reply", "")
    store.set_status(ticket_id, "approved")
    delivery = None
    if reply:  # approve sends whatever draft exists, escalated or not (the old auto_send-only check sent nothing on escalations)
        store.append_message(ticket_id, "agent", reply)  # send: reply joins the thread
        delivery = dispatch_reply(state, reply, ticket_id)  # and out through the source channel
        store.set_lifecycle(ticket_id, "awaiting_customer")  # ball to the customer
        lifecycle = "awaiting_customer"
    else:
        lifecycle = "open"  # escalation stays in our court, nothing sent
    return {"ticket_id": ticket_id, "human_status": "approved", "lifecycle": lifecycle, "delivery": delivery}


@app.post("/tickets/{ticket_id}/reject")
def reject_reply(ticket_id: str, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    store.set_status(ticket_id, "rejected")
    return {"ticket_id": ticket_id, "human_status": "rejected"}


@app.post("/tickets/{ticket_id}/edit")
def edit_reply(ticket_id: str, payload: EditIn, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    store.edit_reply(ticket_id, payload.reply)
    if state.get("human_status") == "sent":
        # already auto-sent: the edit rewrites the sent message in the thread, status stays sent.
        # ceiling: an email/jira copy already left the building; only the thread record is corrected.
        store.replace_last_agent_message(ticket_id, payload.reply)
        store.set_status(ticket_id, "sent")
        return {"ticket_id": ticket_id, "human_status": "sent", "edited_sent_message": True}
    return {"ticket_id": ticket_id, "human_status": "edited"}


@app.get("/metrics")
def get_metrics(user: User = Depends(require_staff)):
    return store.metrics()


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


@app.post("/tickets/{ticket_id}/reply")
def customer_reply(ticket_id: str, payload: ReplyIn, background: BackgroundTasks, user: User = Depends(current_user)):
    ratelimit.check(f"reply:{user.email}", 20, 600)  # replies re-run the pipeline
    state = _require_ticket_access(ticket_id, user)
    _require_open(state)
    store.append_message(ticket_id, "customer", payload.body)  # message thread grows & lifecycle -> open
    background.add_task(_reprocess, ticket_id, payload.body)
    return {"ticket_id": ticket_id, "status": "processing"}


@app.post("/email/sync")
def email_sync(background: BackgroundTasks, user: User = Depends(require_staff)):
    try:
        emails, skipped = fetch_unread()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"email fetch failed: {e}")
    created = []
    for raw in emails:
        ticket_id = f"T-{uuid.uuid4().hex[:8]}"
        store.save_pending(
            ticket_id,
            raw["subject"],
            raw["body"],
            raw["source"],
            raw["name"],
            raw["email"],
            datetime.now(timezone.utc),
        )
        payload = {k: raw[k] for k in ("subject", "body", "source", "name", "email")}
        background.add_task(_process, ticket_id, payload)
        created.append(ticket_id)
    return {"fetched": len(emails), "skipped": skipped, "ticket_ids": created}


@app.post("/jira/sync")
def jira_sync(background: BackgroundTasks, user: User = Depends(require_staff)):
    try:
        issues = jira_channel.fetch_new()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"jira fetch failed: {e}")
    created = []
    for raw in issues:
        ticket_id = f"T-{uuid.uuid4().hex[:8]}"
        store.save_pending(
            ticket_id,
            raw["subject"],
            raw["body"],
            raw["source"],
            raw["name"],
            raw["email"],
            datetime.now(timezone.utc),
        )
        store.add_jira_link(ticket_id, raw["issue_key"])
        payload = {k: raw[k] for k in ("subject", "body", "source", "name", "email")}
        background.add_task(_process, ticket_id, payload)
        created.append({"ticket_id": ticket_id, "issue": raw["issue_key"]})
    return {"fetched": len(issues), "tickets": created}


class ResolveIn(BaseModel):
    csat: int | None = Field(default=None, ge=1, le=10)  # optional 1-10 star rating


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, payload: ResolveIn | None = None, user: User = Depends(current_user)):
    ratelimit.check(f"resolve:{user.email}", 30, 600)  # resolve triggers the learn agent
    state = _require_ticket_access(ticket_id, user)
    csat = payload.csat if payload else None
    if csat is not None:
        store.set_csat(ticket_id, csat)  # record the rating
    if state.get("lifecycle") == "resolved":  # already filed, do not double-write
        return {
            "ticket_id": ticket_id,
            "lifecycle": "resolved",
            "learned": False,
            "note": "already resolved",
            "csat": csat,
        }
    store.set_lifecycle(ticket_id, "resolved")
    _CANCELLED.add(ticket_id)  # kill any in-flight pipeline run for this ticket
    jira_done = None
    issue = store.get_jira_link(ticket_id)
    if issue:
        try:
            jira_done = jira_channel.transition_done(issue)
        except Exception:
            jira_done = False  # their board lagging must never block our resolve
    new_id = store.file_as_history(ticket_id)  # archive FIRST: a KB failure must never strand a ticket
    # write-back the resolution we actually sent (last agent turn), quality-gated
    ticket = Ticket(**state["ticket"])
    agent_msgs = [m["body"] for m in state.get("messages", []) if m["role"] == "agent"]
    resolution = agent_msgs[-1] if agent_msgs else (state.get("draft") or {}).get("reply", "")
    try:
        # nothing to learn from a ticket resolved before any agent reply; skip the LLM call
        out = learn_agent(ticket, resolution, resolved=True) if resolution.strip() else {"learned": False}
    except Exception as e:
        print(f"[resolve] learn failed for {new_id}: {e}", flush=True)
        out = {"learned": False}
    return {
        "ticket_id": new_id,
        "lifecycle": "resolved",
        "learned": out.get("learned", False),
        "csat": csat,
        "jira_done": jira_done,
    }


class AssignIn(BaseModel):
    assignee: str | None = Field(default=None, max_length=120)  # null clears the assignment


@app.post("/tickets/{ticket_id}/assign")
def assign_ticket(ticket_id: str, payload: AssignIn, user: User = Depends(require_staff)):
    # the most basic helpdesk verb: this ticket is MINE (or nobody's again).
    # free-text on purpose: the AI writes names here too, no staff table needed.
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    assignee = (payload.assignee or "").strip() or None
    store.set_assignee(ticket_id, assignee)
    return {"ticket_id": ticket_id, "assignee": assignee}


class TagIn(BaseModel):
    tag: str = Field(min_length=1, max_length=60)


@app.post("/tickets/{ticket_id}/tags")
def add_ticket_tag(ticket_id: str, payload: TagIn, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    store.add_tag(ticket_id, payload.tag)
    return {"ticket_id": ticket_id, "tag": payload.tag, "added": True}


@app.delete("/tickets/{ticket_id}/tags/{tag}")
def remove_ticket_tag(ticket_id: str, tag: str, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    store.remove_tag(ticket_id, tag)
    return {"ticket_id": ticket_id, "tag": tag, "removed": True}


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


@app.post("/tickets/{ticket_id}/note")
def add_internal_note(ticket_id: str, payload: NoteIn, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    _require_open(state)
    store.append_message(ticket_id, "internal", payload.body)
    return {"ticket_id": ticket_id, "role": "internal", "added": True}


@app.get("/tickets/{ticket_id}/thread")
def customer_thread(ticket_id: str, user: User = Depends(current_user)):
    state = _require_ticket_access(ticket_id, user)
    messages = public_messages(state.get("messages", []))
    return {"ticket_id": ticket_id, "messages": messages}


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=20_000)
    category: str | None = Field(default=None, max_length=60)
    keywords: list[str] = []
    auto_use: bool = False


@app.get("/templates")
def list_templates(user: User = Depends(require_staff)):
    return store.list_templates()


@app.post("/templates")
def add_template(payload: TemplateIn, user: User = Depends(require_admin)):
    return store.create_template(payload.name, payload.body, payload.category, payload.keywords, payload.auto_use)


@app.get("/templates/{template_id}")
def read_template(template_id: int, user: User = Depends(require_staff)):
    tpl = store.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    return tpl


@app.put("/templates/{template_id}")
def edit_template(template_id: int, payload: TemplateIn, user: User = Depends(require_admin)):
    tpl = store.update_template(
        template_id,
        payload.name,
        payload.body,
        payload.category,
        payload.keywords,
        payload.auto_use,
    )
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    return tpl


@app.delete("/templates/{template_id}")
def remove_template(template_id: int, user: User = Depends(require_admin)):
    if not store.delete_template(template_id):
        raise HTTPException(status_code=404, detail="template not found")
    return {"template_id": template_id, "deleted": True}


class ApplyTemplateIn(BaseModel):
    template_id: int


@app.post("/tickets/{ticket_id}/apply-template")
def apply_template(ticket_id: str, payload: ApplyTemplateIn, user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    tpl = store.get_template(payload.template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    store.edit_reply(ticket_id, tpl["body"])  # overwrite the draft with the template; marks the ticket 'edited'
    return {
        "ticket_id": ticket_id,
        "applied_template": tpl["name"],
        "reply": tpl["body"],
    }


class MergeIn(BaseModel):
    duplicate_id: str  # this folds INTO the ticket in the path


@app.post("/tickets/{ticket_id}/merge")
def merge_ticket(ticket_id: str, payload: MergeIn, user: User = Depends(require_staff)):
    if not store.merge_tickets(payload.duplicate_id, ticket_id):
        raise HTTPException(
            status_code=400,
            detail="merge failed: both ids must exist, differ, and the duplicate must not already be merged",
        )
    return {"primary": ticket_id, "merged": payload.duplicate_id}


class LinkIn(BaseModel):
    other_id: str


@app.post("/tickets/{ticket_id}/link")
def link_ticket(ticket_id: str, payload: LinkIn, user: User = Depends(require_staff)):
    if not store.link_tickets(ticket_id, payload.other_id):
        raise HTTPException(status_code=400, detail="link failed: both ids must exist and differ")
    return {"linked": sorted([ticket_id, payload.other_id])}


MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5MB ceiling
ALLOWED_ATTACHMENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
}


@app.post("/tickets/{ticket_id}/attachments")
async def upload_attachment(ticket_id: str, file: UploadFile = File(...), user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported type: {file.content_type}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 5 MB)")
    return store.add_attachment(ticket_id, file.filename, file.content_type, data)


@app.get("/tickets/{ticket_id}/attachments")
def list_ticket_attachments(ticket_id: str, user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return store.list_attachments(ticket_id)


@app.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: int, user: User = Depends(require_staff)):
    a = store.get_attachment(attachment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    return Response(
        content=bytes(a["data"]),
        media_type=a["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{a["filename"]}"'},
    )
