"""$0 API gate tests: no database, no model, app driven without startup.

The first guarding test pins the approve escalate-vs-send behaviour: approving
an escalated ticket (empty draft) must send NOTHING, while approving a drafted
reply must join the thread and report a delivery.
Run: uv run --with pytest --with httpx python -m pytest tests/ -q
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

import pytest
from fastapi.testclient import TestClient

import api
from app.users import current_user


def fake_user(role="staff", email="dana@nimbus.dev"):
    return SimpleNamespace(role=role, email=email, is_active=True)


@pytest.fixture
def client():
    yield TestClient(api.app)  # no context manager = no startup: nothing touches Postgres
    api.app.dependency_overrides.clear()


def as_user(user):
    api.app.dependency_overrides[current_user] = lambda: user


def open_state(reply="", source="form", email="priya@elmwoodpress.co"):
    return {
        "ticket": {"subject": "s", "body": "b", "source": source, "customer_email": email},
        "draft": {"reply": reply},
        "lifecycle": "open",
    }


def test_approve_escalation_sends_nothing(client, monkeypatch):
    # escalated ticket = empty draft: approve must not put words in anyone's mouth
    sent = []
    monkeypatch.setattr(api.store, "get", lambda tid: open_state(reply=""))
    monkeypatch.setattr(api.store, "set_status", lambda tid, s: True)
    monkeypatch.setattr(api.store, "append_message", lambda *a: sent.append(a))
    as_user(fake_user())
    r = client.post("/tickets/T-1/approve")
    assert r.status_code == 200
    assert r.json()["delivery"] is None
    assert r.json()["lifecycle"] == "open"
    assert sent == []


def test_approve_draft_sends_and_hands_ball_to_customer(client, monkeypatch):
    sent = []
    monkeypatch.setattr(api.store, "get", lambda tid: open_state(reply="Here is the fix."))
    monkeypatch.setattr(api.store, "set_status", lambda tid, s: True)
    monkeypatch.setattr(api.store, "set_lifecycle", lambda tid, lc: True)
    monkeypatch.setattr(api.store, "append_message", lambda *a: sent.append(a))
    as_user(fake_user())
    r = client.post("/tickets/T-1/approve")
    assert r.status_code == 200
    assert r.json()["delivery"] == "in_app"  # form-source ticket never leaves the app
    assert r.json()["lifecycle"] == "awaiting_customer"
    assert len(sent) == 1


def test_approve_resolved_is_locked(client, monkeypatch):
    state = open_state(reply="x")
    state["lifecycle"] = "resolved"
    monkeypatch.setattr(api.store, "get", lambda tid: state)
    as_user(fake_user())
    assert client.post("/tickets/T-1/approve").status_code == 409


def test_customer_can_file(client, monkeypatch):
    saved = []
    monkeypatch.setattr(api.store, "save_pending", lambda *a: saved.append(a))
    monkeypatch.setattr(api, "_process", lambda *a, **k: None)  # no pipeline in tests
    as_user(fake_user(role="customer"))
    r = client.post("/tickets", json={"subject": "s", "body": "b", "source": "form"})
    assert r.status_code == 200
    assert len(saved) == 1


def test_archive_scope_is_admin_only(client, monkeypatch):
    monkeypatch.setattr(api.store, "list_all", lambda **k: [])
    as_user(fake_user(role="staff"))
    assert client.get("/tickets", params={"scope": "archive"}).status_code == 403
    as_user(fake_user(role="admin"))
    assert client.get("/tickets", params={"scope": "archive"}).status_code == 200


def test_staff_reopen_clears_the_doomed_mark(client, monkeypatch):
    monkeypatch.setattr(api.store, "reopen_from_history", lambda tid: "T-abc12345")
    api._CANCELLED.add("T-abc12345")  # the resolve marked it doomed
    as_user(fake_user(role="staff"))
    r = client.post("/tickets/HIST-abc12345/reopen")
    assert r.status_code == 200
    assert r.json()["ticket_id"] == "T-abc12345"
    assert "T-abc12345" not in api._CANCELLED


def test_reopen_refuses_non_archived(client, monkeypatch):
    monkeypatch.setattr(api.store, "reopen_from_history", lambda tid: None)
    as_user(fake_user(role="staff"))
    assert client.post("/tickets/T-live1234/reopen").status_code == 409


def test_customer_cannot_reopen_someone_elses_ticket(client, monkeypatch):
    monkeypatch.setattr(api.store, "get", lambda tid: open_state(email="other@person.co"))
    as_user(fake_user(role="customer", email="priya@elmwoodpress.co"))
    assert client.post("/my/tickets/HIST-abc12345/reopen").status_code == 403


def test_customer_history_needs_a_real_ticket(client, monkeypatch):
    monkeypatch.setattr(api.store, "get", lambda tid: None)
    as_user(fake_user(role="staff"))
    assert client.get("/tickets/T-ghost123/history").status_code == 404


def test_approve_zendesk_ticket_replies_as_comment(client, monkeypatch):
    posted = {}
    monkeypatch.setattr(api.store, "get", lambda tid: open_state(reply="On its way.", source="zendesk"))
    monkeypatch.setattr(api.store, "set_status", lambda *a: None)
    monkeypatch.setattr(api.store, "append_message", lambda *a: None)
    monkeypatch.setattr(api.store, "set_lifecycle", lambda *a: None)
    monkeypatch.setattr(api.store, "get_zendesk_link", lambda tid: "42")
    monkeypatch.setattr(api.zendesk_channel, "post_comment", lambda zid, body: posted.update({zid: body}))
    as_user(fake_user())
    r = client.post("/tickets/T-1/approve")
    assert r.status_code == 200
    assert r.json()["delivery"] == "zendesk_comment:42"
    assert posted == {"42": "On its way."}
