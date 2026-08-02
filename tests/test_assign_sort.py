"""Manual assignment and queue sorting. $0, no DB: store swapped for fakes."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
from app.users import current_user


def staff():
    return SimpleNamespace(role="staff", email="dana@nimbus.dev", is_active=True)


@pytest.fixture
def client():
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_assign_and_clear(client, monkeypatch):
    calls = []
    monkeypatch.setattr(api.store, "get", lambda tid: {"lifecycle": "open"})
    monkeypatch.setattr(api.store, "set_assignee", lambda tid, a: calls.append((tid, a)) or True)
    api.app.dependency_overrides[current_user] = staff
    assert client.post("/tickets/T-1/assign", json={"assignee": " dana "}).json()["assignee"] == "dana"
    assert client.post("/tickets/T-1/assign", json={"assignee": None}).json()["assignee"] is None
    assert calls == [("T-1", "dana"), ("T-1", None)]


def test_assign_missing_ticket_404s(client, monkeypatch):
    monkeypatch.setattr(api.store, "get", lambda tid: None)
    api.app.dependency_overrides[current_user] = staff
    assert client.post("/tickets/T-x/assign", json={"assignee": "dana"}).status_code == 404


def test_unknown_sort_rejected(client):
    api.app.dependency_overrides[current_user] = staff
    r = client.get("/tickets?sort=evil; DROP TABLE tickets")
    assert r.status_code == 422


def test_sla_sort_reaches_store_as_the_whitelisted_key(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(api.store, "list_all", lambda **kw: seen.update(kw) or [])
    api.app.dependency_overrides[current_user] = staff
    assert client.get("/tickets?sort=sla").status_code == 200
    assert seen["sort"] == "sla"
