"""`GET /jobs?brief=1` drops the long text fields; the default shape is unchanged."""
from backend.tests.r4_support import client, make_job  # noqa: F401 — client is a fixture


def test_brief_drops_long_fields(client, test_db):
    make_job(test_db, title="Brief me", company="Acme", description="x" * 5000,
             scoring_report={"PM": {"summary": "long"}}, h1b_jd_snippet="no sponsorship")
    full = client.get("/api/jobs?limit=5").json()["jobs"][0]
    brief = client.get("/api/jobs?limit=5&brief=1").json()["jobs"][0]
    assert full["description"] and full["scoring_report"]
    for k in ("description", "scoring_report", "h1b_jd_snippet"):
        assert k not in brief
    for k in ("id", "title", "company", "cv_scores", "best_score", "status", "tailored_resume_id", "in_flight"):
        assert k in brief
