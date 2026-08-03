import os

import httpx

from app.adapters import ZendeskAdapter

IMPORT_TAG = "enklima-imported"


def _client() -> httpx.Client:
    sub = os.getenv("ZENDESK_SUBDOMAIN")
    email = os.getenv("ZENDESK_EMAIL")
    token = os.getenv("ZENDESK_API_TOKEN")
    if not all([sub, email, token]):
        raise RuntimeError("ZENDESK_SUBDOMAIN / ZENDESK_EMAIL / ZENDESK_API_TOKEN missing from .env")
    return httpx.Client(
        base_url=f"https://{sub}.zendesk.com/api/v2",
        auth=(f"{email}/token", token),  # Zendesk basic auth: username is "email/token"
        timeout=20,
    )


def fetch_new() -> list[dict]:
    # untagged, unfinished tickets; the tag IS the dedupe (like Jira's label, email's read-flag)
    adapter = ZendeskAdapter()
    with _client() as c:
        r = c.get("/tickets.json", params={"include": "users", "sort_by": "created_at"})
        r.raise_for_status()
        data = r.json()
        users = {u["id"]: u for u in data.get("users", [])}
        out = []
        for t in data.get("tickets", []):
            if IMPORT_TAG in (t.get("tags") or []) or t.get("status") in ("solved", "closed"):
                continue
            requester = users.get(t.get("requester_id"), {})
            raw = adapter.to_canonical({"ticket": {**t, "requester": requester}})
            raw["source"] = "zendesk"  # keep the origin so replies route back as comments
            raw["zendesk_id"] = str(t["id"])
            out.append(raw)
            c.post(f"/tickets/{t['id']}/tags.json", json={"tags": [IMPORT_TAG]}).raise_for_status()
        return out


def post_comment(zendesk_id: str, body: str) -> None:
    with _client() as c:
        c.put(f"/tickets/{zendesk_id}.json", json={"ticket": {"comment": {"body": body, "public": True}}}).raise_for_status()


def mark_solved(zendesk_id: str) -> bool:
    with _client() as c:
        c.put(f"/tickets/{zendesk_id}.json", json={"ticket": {"status": "solved"}}).raise_for_status()
        return True
