from fastapi import FastAPI, HTTPException, BackgroundTasks
import os
import uuid
from datetime import datetime,timezone
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.graph import graph
from app.orchestrator import graph_auto
from app import store
from app.router import MODEL_TIER

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

def _process(ticket_id: str, raw: dict):
    final = active_graph.invoke(
        {"raw_input": {**raw, "ticket_id": ticket_id},"messages":[{"role": "customer", "body": raw["body"]}], "audit": []},
        {"recursion_limit": 40},
    )
    if final.get("ticket") is not None:
        store.save(final)

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

@app.get("/tickets")
def list_tickets():
    return store.list_all()

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
    store.set_status(ticket_id, "approved")
    reply = (state.get("draft") or {}).get("reply", "")
    if reply:
        store.append_message(ticket_id, "agent", reply)   # our reply joins the thread
    store.set_lifecycle(ticket_id, "awaiting_customer")   # ball back to the customer
    return {"ticket_id": ticket_id, "human_status": "approved", "lifecycle": "awaiting_customer"}

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
