from sqlalchemy.orm import sessionmaker

from backend.models.db import Setting


def test_scheduler_registers_speedyapply_cron_with_configured_timezone(test_db, monkeypatch):
    TestSession = sessionmaker(bind=test_db.get_bind())
    session = TestSession()
    session.add_all([
        Setting(key="scrape_interval_minutes", value="0"),
        Setting(key="email_check_interval_minutes", value="0"),
        Setting(key="speedyapply_enabled", value="true"),
        Setting(key="speedyapply_cron", value="30 9 * * *"),
        Setting(key="speedyapply_secondary_cron", value="30 20 * * *"),
        Setting(key="speedyapply_timezone", value="Asia/Shanghai"),
        Setting(key="job_feeds_enabled", value="true"),
    ])
    session.commit()
    session.close()

    import backend.scheduler as sched_mod
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    sched_mod.configure_scheduler()

    job = fresh.get_job("speedyapply_daily")
    secondary_job = fresh.get_job("speedyapply_daily_secondary")
    assert job is not None
    assert secondary_job is not None
    assert job.trigger.timezone.key == "Asia/Shanghai"
    assert secondary_job.trigger.timezone.key == "Asia/Shanghai"
    assert str(job.trigger).startswith("cron[")
    assert "hour='20'" in str(secondary_job.trigger)
    assert "minute='30'" in str(secondary_job.trigger)


def test_scheduler_skips_speedyapply_when_disabled(test_db, monkeypatch):
    TestSession = sessionmaker(bind=test_db.get_bind())
    session = TestSession()
    session.add_all([
        Setting(key="scrape_interval_minutes", value="0"),
        Setting(key="email_check_interval_minutes", value="0"),
        Setting(key="speedyapply_enabled", value="false"),
        Setting(key="speedyapply_cron", value="0 9 * * *"),
    ])
    session.commit()
    session.close()

    import backend.scheduler as sched_mod
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)
    monkeypatch.setattr(sched_mod, "scheduler", fresh)
    sched_mod.configure_scheduler()

    assert fresh.get_job("speedyapply_daily") is None
    assert fresh.get_job("speedyapply_daily_secondary") is None


def test_scheduler_registers_realtime_feeds_and_explicit_speedyapply_crons(test_db, monkeypatch):
    TestSession = sessionmaker(bind=test_db.get_bind())
    session = TestSession()
    session.add_all([
        Setting(key="scrape_interval_minutes", value="0"),
        Setting(key="email_check_interval_minutes", value="0"),
        Setting(key="job_feeds_enabled", value="true"),
        Setting(key="job_feeds_interval_minutes", value="5"),
        Setting(key="job_feeds_worker_interval_minutes", value="1"),
        Setting(key="speedyapply_enabled", value="true"),
        Setting(key="speedyapply_cron", value="0 9 * * *"),
        Setting(key="speedyapply_secondary_cron", value="30 20 * * *"),
    ])
    session.commit()
    session.close()

    import backend.scheduler as sched_mod
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    fresh = AsyncIOScheduler()
    monkeypatch.setattr(sched_mod, "SessionLocal", TestSession)
    monkeypatch.setattr(sched_mod, "scheduler", fresh)

    sched_mod.configure_scheduler()

    poll = fresh.get_job("job_feed_poll")
    worker = fresh.get_job("job_feed_worker")
    assert poll is not None
    assert worker is not None
    assert "0:05:00" in str(poll.trigger)
    assert "0:01:00" in str(worker.trigger)
    assert fresh.get_job("speedyapply_daily") is not None
    assert fresh.get_job("speedyapply_daily_secondary") is not None
