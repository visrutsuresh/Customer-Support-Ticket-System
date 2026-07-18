import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import jira_channel, store
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

store.init_db()  # make sure the tickets table exists when the API boots

# AGENT_MODE toggle: deterministic (fixed LangGraph pipeline) | autonomous (5 ReAct agents + orchestrator)
AGENT_MODE = os.getenv("AGENT_MODE", "deterministic").lower()
active_graph = graph_auto if AGENT_MODE == "autonomous" else graph

app = FastAPI(title="Support Ticket Triage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])


@app.on_event("startup")
async def _startup():
    await create_user_table()


@app.get("/config")
def brand_config():
    # the client company's branding; the portal renders this, Enklima stays vendor-side
    return {
        "brand_name": os.getenv("BRAND_NAME", "Support"),
        "brand_tagline": os.getenv("BRAND_TAGLINE", ""),
    }


class TicketIn(BaseModel):
    subject: str
    body: str
    source: str = "form"
    name: str | None = None
    email: str | None = None


@app.get("/")
def health():
    return {"status": "ok", "mode": AGENT_MODE, "model_tier": MODEL_TIER}


@app.post("/tickets")
def create_ticket(payload: TicketIn, background: BackgroundTasks, user: User = Depends(current_user)):
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


PIPELINE_TIMEOUT_S = 180  # same wall-clock cap bench.py uses


def _invoke_guarded(ticket_id: str, initial: dict):
    # run the graph with a hard time cap so one hung ticket can't jam the background queue.
    # two attempts: a timeout is usually a Modal cold start, and the retry hits a warm container.
    for _attempt in (1, 2):
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


def _process(ticket_id: str, raw: dict):
    final = _invoke_guarded(
        ticket_id,
        {
            "raw_input": {**raw, "ticket_id": ticket_id},
            "messages": [{"role": "customer", "body": raw["body"]}],
            "audit": [],
        },
    )
    if final and final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)
    elif final is not None:
        # graph finished but produced no ticket (e.g. intake rejected): surface it, never strand "processing"
        print(f"[pipeline] {ticket_id} finished without a ticket: {(final.get('decision') or {}).get('reason')}", flush=True)
        store.set_status(ticket_id, "error")


def _reprocess(ticket_id: str, latest: str):
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
    final = _invoke_guarded(ticket_id, {"raw_input": raw, "messages": prior.get("messages", []), "audit": []})
    if final and final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)


def _require_ticket_access(ticket_id: str, user: User) -> dict:
    # staff see everything; a customer only touches tickets born from their email
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if user.role == "customer" and (state["ticket"].get("customer_email") or "").lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="not your ticket")
    return state


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
    user: User = Depends(require_staff),
):
    return store.list_all(status=status, category=category, tag=tag, q=q)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, user: User = Depends(require_staff)):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return state


class EditIn(BaseModel):
    reply: str


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
    decision = state.get("decision") or {}
    reply = (state.get("draft") or {}).get("reply", "")
    store.set_status(ticket_id, "approved")
    delivery = None
    if decision.get("action") == "auto_send" and reply:
        store.append_message(ticket_id, "agent", reply)  # send: reply joins the thread
        delivery = dispatch_reply(state, reply, ticket_id)  # and out through the source channel
        store.set_lifecycle(ticket_id, "awaiting_customer")  # ball to the customer
        lifecycle = "awaiting_customer"
    else:
        lifecycle = "open"  # escalation stays in our court, nothing sent
    return {"ticket_id": ticket_id, "human_status": "approved", "lifecycle": lifecycle, "delivery": delivery}


@app.post("/tickets/{ticket_id}/reject")
def reject_reply(ticket_id: str, user: User = Depends(require_staff)):
    if not store.set_status(ticket_id, "rejected"):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "rejected"}


@app.post("/tickets/{ticket_id}/edit")
def edit_reply(ticket_id: str, payload: EditIn, user: User = Depends(require_staff)):
    if not store.edit_reply(ticket_id, payload.reply):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "edited"}


@app.get("/metrics")
def get_metrics(user: User = Depends(require_staff)):
    return store.metrics()


class ReplyIn(BaseModel):
    body: str


@app.post("/tickets/{ticket_id}/reply")
def customer_reply(ticket_id: str, payload: ReplyIn, background: BackgroundTasks, user: User = Depends(current_user)):
    _require_ticket_access(ticket_id, user)
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
    jira_done = None
    issue = store.get_jira_link(ticket_id)
    if issue:
        try:
            jira_done = jira_channel.transition_done(issue)
        except Exception:
            jira_done = False  # their board lagging must never block our resolve
    # write-back the resolution we actually sent (last agent turn), quality-gated
    ticket = Ticket(**state["ticket"])
    agent_msgs = [m["body"] for m in state.get("messages", []) if m["role"] == "agent"]
    resolution = agent_msgs[-1] if agent_msgs else (state.get("draft") or {}).get("reply", "")
    out = learn_agent(ticket, resolution, resolved=True)
    new_id = store.file_as_history(ticket_id)  # resolved -> past ticket, re-filed under the HIST- prefix
    return {
        "ticket_id": new_id,
        "lifecycle": "resolved",
        "learned": out.get("learned", False),
        "csat": csat,
        "jira_done": jira_done,
    }


class TagIn(BaseModel):
    tag: str


@app.post("/tickets/{ticket_id}/tags")
def add_ticket_tag(ticket_id: str, payload: TagIn, user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.add_tag(ticket_id, payload.tag)
    return {"ticket_id": ticket_id, "tag": payload.tag, "added": True}


@app.delete("/tickets/{ticket_id}/tags/{tag}")
def remove_ticket_tag(ticket_id: str, tag: str, user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.remove_tag(ticket_id, tag)
    return {"ticket_id": ticket_id, "tag": tag, "removed": True}


class NoteIn(BaseModel):
    body: str


@app.post("/tickets/{ticket_id}/note")
def add_internal_note(ticket_id: str, payload: NoteIn, user: User = Depends(require_staff)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.append_message(ticket_id, "internal", payload.body)
    return {"ticket_id": ticket_id, "role": "internal", "added": True}


@app.get("/tickets/{ticket_id}/thread")
def customer_thread(ticket_id: str, user: User = Depends(current_user)):
    state = _require_ticket_access(ticket_id, user)
    messages = public_messages(state.get("messages", []))
    return {"ticket_id": ticket_id, "messages": messages}


class TemplateIn(BaseModel):
    name: str
    body: str
    category: str | None = None
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
