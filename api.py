from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import uuid
from datetime import datetime,timezone
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from app.graph import graph,auto_tags
from app.orchestrator import graph_auto
from app import store
from app.router import MODEL_TIER
from app.agents import learn_agent
from app.state import Ticket, public_messages
from app.intake import normalize

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
    store.save_pending(ticket_id, payload.subject, payload.body,
                       payload.source, payload.name, payload.email,
                       datetime.now(timezone.utc))
    background.add_task(_process, ticket_id, payload.model_dump())
    return {"ticket_id": ticket_id, "status": "processing"}

def _deflect_with_template(ticket_id: str, raw: dict) -> bool:
    # 8b: if an auto_use template keyword hits the very first message, answer with the template
    # directly. no LLM pipeline, no human review, auto-sent. FIRST CONTACT ONLY (a later customer
    # reply goes through _reprocess = the full AI + human path, which is the safety backstop).
    tpl = store.match_auto_template(f"{raw.get('subject','')} {raw.get('body','')}")
    if tpl is None:
        return False
    ticket = normalize({**raw, "ticket_id": ticket_id})
    final = {
        "ticket": ticket,
        "classification": {"category": tpl["category"], "priority": "low",
                           "business_impact": "low", "sentiment": "neutral"},
        "decision": {"action": "auto_send", "reason": f"template deflection: {tpl['name']}"},
        "draft": {"reply": tpl["body"], "kind": "answer", "source": "template"},
        "messages": [{"role": "customer", "body": raw["body"]}],
        "audit": [],
    }
    store.save(final)
    store.set_status(ticket_id, "approved")                 # sent, not awaiting a reviewer
    for tag in auto_tags(final["classification"]):
        store.add_tag(ticket_id, tag)
    store.append_message(ticket_id, "agent", tpl["body"])   # reply joins the thread = sent
    store.set_lifecycle(ticket_id, "awaiting_customer")     # ball back to the customer
    return True

def _process(ticket_id: str, raw: dict):
    if _deflect_with_template(ticket_id, raw):    # 8b: template auto-sent, skip the whole pipeline
        return
    final = active_graph.invoke(
        {"raw_input": {**raw, "ticket_id": ticket_id},"messages":[{"role": "customer", "body": raw["body"]}], "audit": []},
        {"recursion_limit": 40},
    )
    if final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)

def _reprocess(ticket_id: str, latest: str):
    prior = store.get(ticket_id) # has the just appended customer turn + original ticket info
    t = prior["ticket"]
    raw = {
        "ticket_id": ticket_id,
        "subject" : t["subject"],
        "body": latest, #newest reply is the live message the pipeline works on
        "source": t.get("source", "form"),
        "name": t.get("customer_name"),
        "email":t.get("customer_email"),
    }   
    final = active_graph.invoke(
        {"raw_input": raw, "messages": prior.get("messages",[]), "audit": []},{"recursion_limit": 40}
    )
    if final.get("ticket") is not None:
        store.save(final)
        for tag in auto_tags(final.get("classification", {})):
            store.add_tag(ticket_id, tag)

@app.get("/tickets")
def list_tickets(status: str | None = None, category: str |None = None, tag: str | None= None, q: str | None=None):
    return store.list_all(status=status, category=category, tag= tag, q=q)

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
        store.append_message(ticket_id, "agent", reply)   # send: reply joins the thread
        store.set_lifecycle(ticket_id, "awaiting_customer")  # ball to the customer
        lifecycle = "awaiting_customer"
    else:
        lifecycle = "open"                                 # escalation stays in our court, nothing sent
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
        raise HTTPException(status_code = 404, detail = "ticket not found")
    store.append_message(ticket_id,"customer",payload.body) #message thread grows & lifecycle -> open
    background.add_task(_reprocess,ticket_id, payload.body)
    return {"ticket_id": ticket_id, "status" : "processing"}

class ResolveIn(BaseModel):
    csat: int | None = Field(default = None, ge=1, le=10) #optional 1-10 star rating

@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, payload: ResolveIn | None=None):
    state = store.get(ticket_id)
    if state is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    csat = payload.csat if payload else None
    if csat is not None:
        store.set_csat(ticket_id,csat) # record the rating
    if state.get("lifecycle") == "resolved":        # already filed, do not double-write
        return {"ticket_id": ticket_id, "lifecycle": "resolved", "learned": False, "note": "already resolved","csat": csat}
    store.set_lifecycle(ticket_id, "resolved")
    # write-back the resolution we actually sent (last agent turn), quality-gated
    ticket = Ticket(**state["ticket"])
    agent_msgs = [m["body"] for m in state.get("messages", []) if m["role"] == "agent"]
    resolution = agent_msgs[-1] if agent_msgs else (state.get("draft") or {}).get("reply", "")
    out = learn_agent(ticket, resolution, resolved=True)
    return {"ticket_id": ticket_id, "lifecycle": "resolved", "learned": out.get("learned", False),"csat": csat}

class TagIn(BaseModel):
    tag:str

@app.post("/tickets/{ticket_id}/tags")
def add_ticket_tag(ticket_id:str, payload: TagIn):
    if store.get(ticket_id) is None:
        raise HTTPException(status_code = 404, detail ="ticket not found")
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
    store.append_message(ticket_id,"internal", payload.body) 
    return {"ticket_id": ticket_id, "role": "internal", "added": True }

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
    return store.create_template(payload.name, payload.body, payload.category, payload.keywords, payload.auto_use)

@app.get("/templates/{template_id}")
def read_template(template_id: int):
    tpl = store.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template not found")
    return tpl

@app.put("/templates/{template_id}")
def edit_template(template_id: int, payload: TemplateIn):
    tpl = store.update_template(template_id, payload.name, payload.body, payload.category, payload.keywords, payload.auto_use)
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
    store.edit_reply(ticket_id, tpl["body"])   # overwrite the draft with the template; marks the ticket 'edited'
    return {"ticket_id": ticket_id, "applied_template": tpl["name"], "reply": tpl["body"]}