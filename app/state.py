from datetime import datetime
from pydantic import BaseModel
from typing import Literal

class Ticket(BaseModel):
    ticket_id: str #unique id for this ticket
    source: Literal["form", "email", "voice_transcript"] #only these exact strings are allowed as input
    subject: str #short title
    body: str #the normalised message text
    customer_id: str | None=None
    created_at: datetime
    raw: dict = {} #holds the untouched original payload, in case we need it for audit