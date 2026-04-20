"""Tests for scheduler.configure_scheduler — interval + cron + reconfig behavior."""
import pytest
from unittest.mock import MagicMock


def test_configure_scheduler_zero_interval_skips_job(test_db, monkeypatch):
    """scrape_interval_minutes=0 → no 'scrape_all' job added."""
    from backend.models.db import Setting
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())

    # Seed with disabled scrape interval
    s = TestSession()
    s.add(Setting(key="scrape_interval_minutes", value="0"))
    s.add(Setting(key="email_check_interval_minutes", value="0"))
    s.commit()
    s.close()

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)

    # Use a fresh scheduler so tests don't pollute each other
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    sched_mod.configure_scheduler()

    job_ids = {j.id for j in fresh.get_jobs()}
    assert "scrape_all" not in job_ids
    assert "email_check" not in job_ids


def test_configure_scheduler_adds_interval_job(test_db, monkeypatch):
    """scrape_interval_minutes=30 → 'scrape_all' job registered."""
    from backend.models.db import Setting
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())

    s = TestSession()
    s.add(Setting(key="scrape_interval_minutes", value="30"))
    s.add(Setting(key="email_check_interval_minutes", value="0"))
    s.commit()
    s.close()

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    sched_mod.configure_scheduler()

    job_ids = {j.id for j in fresh.get_jobs()}
    assert "scrape_all" in job_ids


def test_configure_scheduler_empty_cron_skips(test_db, monkeypatch):
    """Empty cron string → no cron job added."""
    from backend.models.db import Setting
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())

    s = TestSession()
    s.add(Setting(key="scrape_interval_minutes", value="0"))
    s.add(Setting(key="email_check_interval_minutes", value="0"))
    s.add(Setting(key="backup_cron", value=""))
    s.add(Setting(key="digest_cron", value=""))
    s.commit()
    s.close()

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    sched_mod.configure_scheduler()

    job_ids = {j.id for j in fresh.get_jobs()}
    assert "db_backup" not in job_ids
    assert "daily_digest" not in job_ids


def test_configure_scheduler_invalid_cron_logs_warning(test_db, monkeypatch, caplog):
    """Invalid cron (wrong field count) → logs warning, skips job, does NOT crash."""
    import logging
    from backend.models.db import Setting
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())

    s = TestSession()
    s.add(Setting(key="scrape_interval_minutes", value="0"))
    s.add(Setting(key="email_check_interval_minutes", value="0"))
    s.add(Setting(key="backup_cron", value="invalid"))  # 1 field, not 5
    s.commit()
    s.close()

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    with caplog.at_level(logging.WARNING, logger="jobnavigator.scheduler"):
        sched_mod.configure_scheduler()  # must not raise

    job_ids = {j.id for j in fresh.get_jobs()}
    assert "db_backup" not in job_ids
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("cron" in r.message.lower() for r in warnings)


def test_configure_scheduler_calls_remove_all_jobs(test_db, monkeypatch):
    """Re-configuring should call scheduler.remove_all_jobs() first."""
    from backend.models.db import Setting
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=test_db.get_bind())

    s = TestSession()
    s.add(Setting(key="scrape_interval_minutes", value="0"))
    s.add(Setting(key="email_check_interval_minutes", value="0"))
    s.commit()
    s.close()

    import backend.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)

    mock_scheduler = MagicMock()
    mock_scheduler.get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(sched_mod, "scheduler", mock_scheduler)

    sched_mod.configure_scheduler()

    mock_scheduler.remove_all_jobs.assert_called_once()
