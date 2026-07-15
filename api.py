import os
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import store
from app.agents import learn_agent
from app.graph import auto_tags, graph
from app.orchestrator import graph_auto
from app.router import MODEL_TIER
from app.state import Ticket, public_messages

store.init_db()  # make sure the tickets table exists when the API boots

# AGENT_MODE toggle: deterministic (fixed LangGraph pipeline) | autonomous (5 ReAct agents + orchestrator)
AGENT_MODE = os.getenv("AGENT_MODE", "deterministic").lower()
active_graph = graph_auto if AGENT_MODE == "autonomous" else graph

app = FastAPI(title="Support Ticket Triage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def create_ticket(payload: TicketIn, background: BackgroundTasks):
    ticket_id = f"T-{uuid.uuid4().hex[:8]}"
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


def _process(ticket_id: str, raw: dict):
    final = active_graph.invoke(
        {
            "raw_input": {**raw, "ticket_id": ticket_id},
            "messages": [{"role": "customer", "body": raw["body"]}],
            "audit": [],
        },
        {"recursion_limit": 40},
    )
    if final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)


def _reprocess(ticket_id: str, latest: str):
    prior = store.get(
        ticket_id
    )  # has the just appended customer turn + original ticket info
    t = prior["ticket"]
    raw = {
        "ticket_id": ticket_id,
        "subject": t["subject"],
        "body": latest,  # newest reply is the live message the pipeline works on
        "source": t.get("source", "form"),
        "name": t.get("customer_name"),
        "email": t.get("customer_email"),
    }
    final = active_graph.invoke(
        {"raw_input": raw, "messages": prior.get("messages", []), "audit": []},
        {"recursion_limit": 40},
    )
    if final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)
        if (final.get("decision") or {}).get("action") == "escalate":
            _ack_escalation(ticket_id)


@app.get("/tickets")
def list_tickets(
    status: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
):
    return store.list_all(status=status, category=category, tag=tag, q=q)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return state


class EditIn(BaseModel):
    reply: str


@app.post("/tickets/{ticket_id}/approve")
def approve_reply(ticket_id: str):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    decision = state.get("decision") or {}
    reply = (state.get("draft") or {}).get("reply", "")
    store.set_status(ticket_id, "approved")
    if decision.get("action") == "auto_send" and reply:
        store.append_message(ticket_id, "agent", reply)  # send: reply joins the thread
        store.set_lifecycle(ticket_id, "awaiting_customer")  # ball to the customer
        lifecycle = "awaiting_customer"
    else:
        lifecycle = "open"  # escalation stays in our court, nothing sent
    return {"ticket_id": ticket_id, "human_status": "approved", "lifecycle": lifecycle}


@app.post("/tickets/{ticket_id}/reject")
def reject_reply(ticket_id: str):
    if not store.set_status(ticket_id, "rejected"):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "rejected"}


@app.post("/tickets/{ticket_id}/edit")
def edit_reply(ticket_id: str, payload: EditIn):
    if not store.edit_reply(ticket_id, payload.reply):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "edited"}


@app.get("/metrics")
def get_metrics():
    return store.metrics()


class ReplyIn(BaseModel):
    body: str


@app.post("/tickets/{ticket_id}/reply")
def customer_reply(ticket_id: str, payload: ReplyIn, background: BackgroundTasks):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.append_message(
        ticket_id, "customer", payload.body
    )  # message thread grows & lifecycle -> open
    background.add_task(_reprocess, ticket_id, payload.body)
    return {"ticket_id": ticket_id, "status": "processing"}


class ResolveIn(BaseModel):
    csat: int | None = Field(default=None, ge=1, le=10)  # optional 1-10 star rating


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, payload: ResolveIn | None = None):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
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
    # write-back the resolution we actually sent (last agent turn), quality-gated
    ticket = Ticket(**state["ticket"])
    agent_msgs = [m["body"] for m in state.get("messages", []) if m["role"] == "agent"]
    resolution = (
        agent_msgs[-1] if agent_msgs else (state.get("draft") or {}).get("reply", "")
    )
    out = learn_agent(ticket, resolution, resolved=True)
    return {
        "ticket_id": ticket_id,
        "lifecycle": "resolved",
        "learned": out.get("learned", False),
        "csat": csat,
    }


class TagIn(BaseModel):
    tag: str


@app.post("/tickets/{ticket_id}/tags")
def add_ticket_tag(ticket_id: str, payload: TagIn):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.add_tag(ticket_id, payload.tag)
    return {"ticket_id": ticket_id, "tag": payload.tag, "added": True}


@app.delete("/tickets/{ticket_id}/tags/{tag}")
def remove_ticket_tag(ticket_id: str, tag: str):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.remove_tag(ticket_id, tag)
    return {"ticket_id": ticket_id, "tag": tag, "removed": True}


class NoteIn(BaseModel):
    body: str


@app.post("/tickets/{ticket_id}/note")
def add_internal_note(ticket_id: str, payload: NoteIn):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    store.append_message(ticket_id, "internal", payload.body)
    return {"ticket_id": ticket_id, "role": "internal", "added": True}


@app.get("/tickets/{ticket_id}/thread")
def customer_thread(ticket_id: str):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    messages = public_messages(state.get("messages", []))
    return {"ticket_id": ticket_id, "messages": messages}


class TemplateIn(BaseModel):
    name: str
    body: str
    category: str | None = None
    keywords: list[str] = []
    auto_use: bool = False


@app.get("/templates")
def list_templates():
    return store.list_templates()


@app.post("/templates")
def add_template(payload: TemplateIn):
    return store.create_template(
        payload.name, payload.body, payload.category, payload.keywords, payload.auto_use
    )


@app.get("/templates/{template_id}")
def read_template(template_id: int):
    tpl = store.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    return tpl


@app.put("/templates/{template_id}")
def edit_template(template_id: int, payload: TemplateIn):
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
def remove_template(template_id: int):
    if not store.delete_template(template_id):
        raise HTTPException(status_code=404, detail="template not found")
    return {"template_id": template_id, "deleted": True}


class ApplyTemplateIn(BaseModel):
    template_id: int


@app.post("/tickets/{ticket_id}/apply-template")
def apply_template(ticket_id: str, payload: ApplyTemplateIn):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    tpl = store.get_template(payload.template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    store.edit_reply(
        ticket_id, tpl["body"]
    )  # overwrite the draft with the template; marks the ticket 'edited'
    return {
        "ticket_id": ticket_id,
        "applied_template": tpl["name"],
        "reply": tpl["body"],
    }


class MergeIn(BaseModel):
    duplicate_id: str  # this folds INTO the ticket in the path


@app.post("/tickets/{ticket_id}/merge")
def merge_ticket(ticket_id: str, payload: MergeIn):
    if not store.merge_tickets(payload.duplicate_id, ticket_id):
        raise HTTPException(
            status_code=400,
            detail="merge failed: both ids must exist, differ, and the duplicate must not already be merged",
        )
    return {"primary": ticket_id, "merged": payload.duplicate_id}


class LinkIn(BaseModel):
    other_id: str


@app.post("/tickets/{ticket_id}/link")
def link_ticket(ticket_id: str, payload: LinkIn):
    if not store.link_tickets(ticket_id, payload.other_id):
        raise HTTPException(
            status_code=400, detail="link failed: both ids must exist and differ"
        )
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
async def upload_attachment(ticket_id: str, file: UploadFile = File(...)):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"unsupported type: {file.content_type}"
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 5 MB)")
    return store.add_attachment(ticket_id, file.filename, file.content_type, data)


@app.get("/tickets/{ticket_id}/attachments")
def list_ticket_attachments(ticket_id: str):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return store.list_attachments(ticket_id)


@app.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: int):
    a = store.get_attachment(attachment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    return Response(
        content=bytes(a["data"]),
        media_type=a["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{a["filename"]}"'},
    )
