import uuid
from datetime import datetime

from app.state import Ticket


def normalize(raw: dict) -> Ticket:
    """Turn a raw input payload into a canonical Ticket"""
    source = raw["source"]
    if source == "voice_transcript":
        body = raw["transcript"]
        subject = " ".join(body.split()[:6])
    else:
        subject = raw["subject"]
        body = raw["body"]
    return Ticket(
        ticket_id=raw.get("ticket_id") or f"T-{uuid.uuid4().hex[:8]}",
        source=source,
        subject=subject,
        body=body,
        customer_id=raw.get("customer_id"),
        customer_name=raw.get("name") or raw.get("customer_name"),
        customer_email=raw.get("email"),
        created_at=datetime.now(),
        raw=raw,
    )
