"""The daily telemetry send: registered with the other jobs, a day after the last send."""
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import sessionmaker

from backend.tests.r4_support import client, set_setting  # noqa: F401  (client is a fixture)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def _sched(test_db, monkeypatch):
    import backend.scheduler as S
    monkeypatch.setattr(S, "SessionLocal", sessionmaker(bind=test_db.get_bind()))
    fresh = AsyncIOScheduler()
    monkeypatch.setattr(S, "scheduler", fresh)
    return S, fresh


def test_daily_job_is_registered(test_db, monkeypatch):
    S, fresh = _sched(test_db, monkeypatch)
    S.configure_scheduler()
    assert fresh.get_job("telemetry_daily") is not None


def test_restart_within_a_day_does_not_resend(test_db, monkeypatch):
    S, _ = _sched(test_db, monkeypatch)
    set_setting(test_db, "telemetry_last_sent_at", (NOW - timedelta(hours=2)).isoformat())
    assert S.next_telemetry_time(now=NOW) == NOW + timedelta(hours=22)


def test_overdue_or_never_sent_runs_three_minutes_after_start(test_db, monkeypatch):
    S, _ = _sched(test_db, monkeypatch)
    assert S.next_telemetry_time(now=NOW) == NOW + timedelta(minutes=3)
    set_setting(test_db, "telemetry_last_sent_at", (NOW - timedelta(days=3)).isoformat())
    assert S.next_telemetry_time(now=NOW) == NOW + timedelta(minutes=3)


def test_a_broken_stamp_does_not_stop_the_schedule(test_db, monkeypatch):
    S, _ = _sched(test_db, monkeypatch)
    set_setting(test_db, "telemetry_last_sent_at", "yesterday-ish")
    assert S.next_telemetry_time(now=NOW) == NOW + timedelta(minutes=3)


def test_choosing_a_level_reschedules(test_db, monkeypatch):
    """The owner's first choice brings the first send forward (it was a day out while unset)."""
    from backend.api import routes_settings as R
    calls = []
    monkeypatch.setattr(R, "configure_scheduler", lambda: calls.append(1))
    R.update_settings({"telemetry_level": "full"}, db=test_db)
    assert calls == [1]


def test_the_telemetry_job_is_not_listed_in_the_schedule_table(client, test_db, monkeypatch):
    from types import SimpleNamespace
    from apscheduler.triggers.interval import IntervalTrigger
    import backend.scheduler as S

    def job(job_id, minutes):
        return SimpleNamespace(id=job_id, name=job_id, trigger=IntervalTrigger(minutes=minutes),
                               next_run_time=None, pending=False)

    monkeypatch.setattr(S, "scheduler", SimpleNamespace(get_jobs=lambda: [job("telemetry_daily", 1440),
                                                                       job("email_check", 60)]))
    resp = client.get("/api/scheduler/jobs")
    assert resp.status_code == 200, resp.text
    ids = {row["id"] for row in resp.json()}
    assert "telemetry_daily" not in ids          # it runs on its schedule, but the Stats table does not list it
    assert "email_check" in ids
