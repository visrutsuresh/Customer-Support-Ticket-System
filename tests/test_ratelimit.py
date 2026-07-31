import pytest
from fastapi import HTTPException

import app.ratelimit as rl


def test_window_blocks_then_recovers(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock[0])
    for _ in range(3):
        rl.check("k", 3, 60)
    with pytest.raises(HTTPException) as e:
        rl.check("k", 3, 60)
    assert e.value.status_code == 429
    clock[0] = 61.0
    rl.check("k", 3, 60)  # window expired, allowed again


def test_keys_are_independent(monkeypatch):
    monkeypatch.setattr(rl.time, "monotonic", lambda: 0.0)
    rl.check("a", 1, 60)
    rl.check("b", 1, 60)  # b's budget untouched by a
