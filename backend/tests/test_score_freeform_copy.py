"""RES-20: a copy tailored from a pasted job description is still scoreable.

Such a copy has no Job row, so the JD it was written against is kept on the copy
itself (json_data["_tailor_context"]) and the score lands on the copy
(json_data["_score"]) instead of on a job's cv_scores.
"""
import pytest

from backend.models.db import Resume, Job, Setting


def _seed_llm(monkeypatch, payload):
    """Stub the scorer's LLM the way the other scoring tests do."""
    async def fake_call_llm(prompt, system, max_tokens, cached_prefix=None, **kwargs):
        return {
            "text": payload,
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "cache_read_tokens": 0, "cache_write_tokens": 0},
        }
    monkeypatch.setattr("backend.analyzer.cv_scorer.call_llm", fake_call_llm)
    monkeypatch.setattr("backend.analyzer.cv_scorer.log_llm_call", lambda **kw: None)
    import backend.analyzer.cv_scorer as cv_scorer
    monkeypatch.setattr(cv_scorer, "_scoring_semaphore", None, raising=False)


def _rich_copy(**kw):
    """A copy with enough text to clear the 50-char pre-check."""
    return Resume(
        name="Base → (tailored)",
        is_base=False,
        template="inter",
        json_data={
            "summary": "Senior product manager with a decade of fintech platform work",
            "experience": [
                {"company": "Additiv", "title": "Senior PM", "date": "2020",
                 "bullets": ["shipped the wealth platform to eight banks"]},
            ],
            "skills": {"core": "Python, SQL"},
            **kw,
        },
    )


@pytest.mark.asyncio
async def test_score_impl_scores_a_job_less_copy_from_its_saved_jd(test_db, monkeypatch):
    _seed_llm(monkeypatch, '{"scores":{"Tailored":81},"best_cv":"Tailored"}')

    copy = _rich_copy(_tailor_context={"job_description": "Hiring a senior PM for a payments team",
                                       "source": "freeform"})
    test_db.add(copy)
    test_db.commit()
    rid = str(copy.id)

    from backend.api.routes_resumes import _score_resume_impl
    await _score_resume_impl(rid, "light")

    test_db.expire_all()
    stored = test_db.query(Resume).filter(Resume.id == copy.id).first()
    assert stored.json_data["_score"]["Tailored"] == 81
    assert stored.json_data["_score"]["scored_at"]
    # the JD it was scored against is untouched
    assert stored.json_data["_tailor_context"]["source"] == "freeform"


@pytest.mark.asyncio
async def test_score_impl_stores_the_full_report_on_the_copy(test_db, monkeypatch):
    # depth="full" builds _scoring_report from the report keys the schema asks for
    _seed_llm(monkeypatch, '{"scores":{"Tailored":64},"best_cv":"Tailored",'
                           '"summary":"strong payments fit","ats_tip":"mirror the JD wording"}')

    copy = _rich_copy(_tailor_context={"job_description": "Payments PM, fintech", "source": "freeform"})
    test_db.add(copy)
    test_db.commit()
    rid = str(copy.id)

    from backend.api.routes_resumes import _score_resume_impl
    await _score_resume_impl(rid, "full")

    test_db.expire_all()
    stored = test_db.query(Resume).filter(Resume.id == copy.id).first()
    entry = stored.json_data["_score"]
    assert entry["Tailored"] == 64
    assert entry["report"]["scored_with"] == "Tailored"


@pytest.mark.asyncio
async def test_score_impl_skips_a_copy_with_neither_job_nor_jd(test_db, monkeypatch):
    _seed_llm(monkeypatch, '{"scores":{"Tailored":90}}')

    copy = _rich_copy()          # no job_id, no _tailor_context
    test_db.add(copy)
    test_db.commit()
    rid = str(copy.id)

    from backend.api.routes_resumes import _score_resume_impl
    await _score_resume_impl(rid, "light")

    test_db.expire_all()
    stored = test_db.query(Resume).filter(Resume.id == copy.id).first()
    assert "_score" not in (stored.json_data or {})


def test_score_check_accepts_a_job_less_copy_with_a_saved_jd(api_client, test_db, monkeypatch):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    copy = _rich_copy(_tailor_context={"job_description": "Payments PM", "source": "freeform"})
    test_db.add(copy)
    test_db.commit()

    launched = {}

    def fake_launch(job_type, func, **kw):
        launched.update(job_type=job_type, **kw)
        return "run-1"

    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "launch_background", fake_launch)

    r = api_client.post(f"/api/resumes/{copy.id}/score-check", json={"depth": "light"})
    assert r.status_code == 202, r.text
    # the run is scoped to the résumé alone, with no target job
    assert launched["scope_key"] == f"resume:{copy.id}"
    assert launched["target_job_id"] is None


def test_score_check_400s_a_copy_with_neither(api_client, test_db):
    test_db.add(Setting(key="dashboard_api_key", value=""))
    copy = _rich_copy()
    test_db.add(copy)
    test_db.commit()

    r = api_client.post(f"/api/resumes/{copy.id}/score-check", json={"depth": "light"})
    assert r.status_code == 400
    assert "no linked job" in r.json()["detail"]


def test_linked_job_path_is_unchanged(api_client, test_db, monkeypatch):
    """The Job-backed score-check still scopes to the job and passes its uuid."""
    test_db.add(Setting(key="dashboard_api_key", value=""))
    job = Job(external_id="rf1", content_hash="rf1c", company="Acme", title="PM",
              description="Looking for a senior PM with payments experience")
    test_db.add(job)
    test_db.flush()
    copy = _rich_copy()
    copy.job_id = job.id
    test_db.add(copy)
    test_db.commit()

    launched = {}

    def fake_launch(job_type, func, **kw):
        launched.update(job_type=job_type, **kw)
        return "run-2"

    import backend.api.routes_resumes as rr
    monkeypatch.setattr(rr, "launch_background", fake_launch)

    r = api_client.post(f"/api/resumes/{copy.id}/score-check", json={"depth": "light"})
    assert r.status_code == 202, r.text
    assert launched["scope_key"] == f"{job.id}:resume:{copy.id}"
    assert str(launched["target_job_id"]) == str(job.id)


def test_render_html_never_sees_underscore_keys(monkeypatch):
    """The PDF template is handed résumé content only — never _tailor_context/_score."""
    import backend.api.routes_resumes as rr

    seen = {}

    class _Tpl:
        def render(self, **kw):
            seen.update(kw)
            return "<html></html>"

    class _Env:
        def __init__(self, *a, **k):
            self.filters = {}

        def get_template(self, name):
            return _Tpl()

    monkeypatch.setattr("jinja2.Environment", _Env)
    monkeypatch.setattr(rr, "_load_template_fonts", lambda p: {})
    monkeypatch.setattr(rr.Path, "exists", lambda self: True)

    rr._render_html({"summary": "s", "_tailor_context": {"job_description": "x"},
                     "_score": {"Tailored": 70}}, "inter", "letter")

    assert seen["summary"] == "s"
    assert "_tailor_context" not in seen
    assert "_score" not in seen
