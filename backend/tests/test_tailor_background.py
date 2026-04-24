"""Tailoring semaphore + background-job behavior (Task 3 of 12)."""
import asyncio
import pytest
from unittest.mock import AsyncMock

from backend.models.db import Setting


def test_semaphore_default_is_two(test_db, monkeypatch):
    """Absent setting → limit 2."""
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)
    sem = rr._get_tailoring_semaphore()
    assert sem._value == 2


def test_semaphore_reads_setting(test_db, monkeypatch):
    """Setting override is honored."""
    test_db.add(Setting(key="tailoring_max_concurrent", value="5"))
    test_db.commit()
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", None, raising=False)
    sem = rr._get_tailoring_semaphore()
    assert sem._value == 5


def test_reset_clears_cached_semaphore(monkeypatch):
    """reset_tailoring_semaphore() forces re-read on next call."""
    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "_tailoring_semaphore", asyncio.Semaphore(99), raising=False)
    rr.reset_tailoring_semaphore()
    assert rr._tailoring_semaphore is None
