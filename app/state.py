from datetime import datetime
from pydantic import BaseModel
from typing import Literal, TypedDict, Annotated
from operator import add

class Ticket(BaseModel):
    ticket_id: str #unique id for this ticket
    source: Literal["chat","form", "email", "voice_transcript"] #only these exact strings are allowed as input
    subject: str #short title
    body: str #the normalised message text
    customer_id: str | None=None
    created_at: datetime
    raw: dict = {} #holds the untouched original payload, in case we need it for audit

class State(TypedDict):
    ticket: Ticket
    classification: dict  #agent 1's work
    routing:dict #the model-router's choice
    retrieval: dict #agent 2's KB snippets
    draft: dict #agent 3's reply
    compliance:dict #agent 4's pass/fail
    decision: dict #auto send vs escalate
    review_count: int #how many times the review gate has run (caps the regen retry)
    audit: Annotated[list,add]  #append only to make ticket longer
    raw_input: dict #the messy inbound payload, before intake turns it into a Ticket
    error: str | None #why the intake rejected this input
    