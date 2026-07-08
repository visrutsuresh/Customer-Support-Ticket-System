from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.graph import graph
from app import store

store.init_db()  # make sure the tickets table exists when the API boots

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
    return {"status": "ok"}

@app.post("/tickets")
def create_ticket(payload: TicketIn):
    final = graph.invoke({"raw_input": payload.model_dump(), "audit": []})
    if final.get("ticket") is not None:
        store.save(final)
    return final

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
def approve_ticket(ticket_id: str):
    if not store.set_status(ticket_id, "approved"):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "approved"}

@app.post("/tickets/{ticket_id}/reject")
def reject_ticket(ticket_id: str):
    if not store.set_status(ticket_id, "rejected"):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "rejected"}

@app.post("/tickets/{ticket_id}/edit")
def edit_ticket(ticket_id: str, payload: EditIn):
    if not store.edit_reply(ticket_id, payload.reply):
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "human_status": "edited"}
