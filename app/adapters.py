from typing import Protocol


class TicketingAdapter(Protocol):
    """Contract every external ticketing system implements.

    to_canonical maps that system's native payload into the raw dict that
    app.intake.normalize() already understands (source/subject/body/...).
    Zendesk is implemented below; Jira and ServiceNow would be new classes
    with the same method and a different field map. No real API calls here:
    this is the integration SEAM (req 29), not a live integration.
    """
    def to_canonical(self, payload: dict) -> dict: ...


# Zendesk's channel names -> our four allowed source values
_ZENDESK_CHANNEL = {"email": "email", "chat": "chat", "web": "form", "api": "form"}


class ZendeskAdapter:
    """Maps a Zendesk ticket payload into our canonical raw dict."""

    def to_canonical(self, payload: dict) -> dict:
        t = payload["ticket"]
        r = t.get("requester", {})
        channel = t.get("via", {}).get("channel", "web")
        return {
            "source": _ZENDESK_CHANNEL.get(channel, "form"),  # unknown -> form
            "subject": t["subject"],
            "body": t["description"],          # Zendesk calls the body "description"
            "customer_id": str(r["id"]) if r.get("id") is not None else None,
            "name": r.get("name"),
            "email": r.get("email"),
        }
