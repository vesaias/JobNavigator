"""Saving a job triggers scoring as a TRACKED op (launch_background) so dashboard monitors/toasts can see it, but only when on_save_action enables it and the job isn't already scored."""
import uuid
import pytest
from backend.models.db import Setting, Job


def _seed(test_db, on_save="light"):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    test_db.add(Setting(key="on_save_action", value=on_save))
    test_db.commit()


def _job(test_db, cv_scores=None):
    j = Job(id=uuid.uuid4(), external_id=uuid.uuid4().hex, company="Acme", title="PM",
            status="new", saved=False, cv_scores=cv_scores)
    test_db.add(j)
    test_db.commit()
    return j


@pytest.fixture(autouse=True)
def _noop_scorer(monkeypatch):
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr("backend.analyzer.cv_scorer.score_single_job", _noop, raising=True)


def _capture_launch(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.api.routes_jobs.launch_background",
                        lambda *a, **k: calls.append((a, k)) or "run-x", raising=True)
    return calls


def test_update_job_is_async():
    """launch_background() needs a running event loop, so the PATCH handler must stay `async def` — a sync endpoint runs in a threadpool with no loop and the scoring task silently fails to register."""
    import inspect
    from backend.api.routes_jobs import update_job
    assert inspect.iscoroutinefunction(update_job), "update_job must be `async def`"


def test_save_launches_tracked_analyze(api_client, test_db, monkeypatch):
    _seed(test_db, on_save="light")
    job = _job(test_db)
    calls = _capture_launch(monkeypatch)

    resp = api_client.patch(f"/api/jobs/{job.id}", json={"saved": True})
    assert resp.status_code == 200
    assert len(calls) == 1, "save should launch exactly one tracked scoring op"
    args, kwargs = calls[0]
    assert args[0] == "analyze_job"
    assert str(kwargs["target_job_id"]) == str(job.id)
    assert kwargs["func_kwargs"]["depth"] == "light"


def test_save_does_not_launch_when_setting_off(api_client, test_db, monkeypatch):
    _seed(test_db, on_save="off")
    job = _job(test_db)
    calls = _capture_launch(monkeypatch)

    resp = api_client.patch(f"/api/jobs/{job.id}", json={"saved": True})
    assert resp.status_code == 200
    assert calls == [], "on_save_action=off must not launch scoring"


def test_save_does_not_launch_when_already_scored(api_client, test_db, monkeypatch):
    _seed(test_db, on_save="light")
    job = _job(test_db, cv_scores={"Resume A": 72})
    calls = _capture_launch(monkeypatch)

    resp = api_client.patch(f"/api/jobs/{job.id}", json={"saved": True})
    assert resp.status_code == 200
    assert calls == [], "an already-scored job must not re-score on save"
