import csv
import json
from pathlib import Path

import pytest

from backend.automation.application_packets import export_application_packet
from backend.automation.speedyapply_pipeline import _tailor_resume
from backend.models.db import ApplicationQueueItem, Job, JobFeedPosting, Persona, Resume, Setting


def _resume_data(extra_skill=""):
    skills = "Python, SQL" + (f", {extra_skill}" if extra_skill else "")
    return {
        "header": {"name": "Candidate", "contact_items": [{"text": "candidate@example.com", "url": ""}]},
        "summary": "Software engineer",
        "experience": [{
            "company": "Acme",
            "title": "Software Engineer Intern",
            "location": "California",
            "date": "2025",
            "bullets": ["Built Python APIs used by 100 users"],
        }],
        "skills": {"Languages": skills},
        "education": [{"school": "UC", "degree": "BS Computer Science"}],
    }


def _packet_rows(test_db, artifact_root, *, tailored=None):
    base = _resume_data()
    persona = Persona(id=1, contact={"email": "candidate@example.com"}, resume_content=base)
    job = Job(
        external_id="packet-job",
        content_hash="packet-content",
        company="Example Corp",
        title="Software Engineer Intern",
        location="San Francisco, CA",
        url="https://jobs.example.com/packet",
        description="Build Python APIs and distributed systems.",
    )
    test_db.add_all([
        persona,
        job,
        Setting(key="job_feeds_artifact_dir", value=str(artifact_root)),
    ])
    test_db.flush()
    resume = Resume(
        name="Persona -> Example Corp",
        is_base=False,
        job_id=job.id,
        json_data=tailored or base,
    )
    test_db.add(resume)
    test_db.flush()
    item = ApplicationQueueItem(
        job_id=job.id,
        resume_id=resume.id,
        source_feed="speedyapply_intern_usa",
        application_url=job.url,
        status="exporting",
    )
    test_db.add(item)
    test_db.flush()
    test_db.add(JobFeedPosting(
        source_id="speedyapply_intern_usa",
        repository_id="speedyapply_2027",
        source_key="url:packet",
        job_id=job.id,
        source_url=job.url,
    ))
    test_db.commit()
    return item


@pytest.mark.asyncio
async def test_packet_export_writes_stable_mapping_and_index(test_db, tmp_path, monkeypatch):
    item = _packet_rows(test_db, tmp_path / "application-packets")

    async def fake_render(resume, db):
        return b"fake-pdf", 1, "Candidate_Resume"

    monkeypatch.setattr("backend.api.routes_resumes.render_resume_pdf_bytes", fake_render)
    monkeypatch.setattr(
        "backend.automation.application_packets._extract_pdf_text",
        lambda value: "Candidate Software Engineer Experience Python APIs " * 5,
    )

    metadata = await export_application_packet(str(item.id))
    test_db.expire_all()
    refreshed = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item.id).one()
    packet_dir = Path(refreshed.artifact_dir)

    assert refreshed.status == "ready"
    assert metadata["job_id"] == str(item.job_id)
    assert (packet_dir / "resume.pdf").read_bytes() == b"fake-pdf"
    saved = json.loads((packet_dir / "metadata.json").read_text(encoding="utf-8"))
    assert saved["queue_item_id"] == str(item.id)
    with (tmp_path / "application-packets" / "index.csv").open(encoding="utf-8-sig", newline="") as handle:
        index_rows = list(csv.DictReader(handle))
    assert index_rows[0]["job_id"] == str(item.job_id)
    assert index_rows[0]["resume_id"] == str(item.resume_id)


@pytest.mark.asyncio
async def test_packet_marks_new_skill_and_multipage_pdf_needs_review(test_db, tmp_path, monkeypatch):
    item = _packet_rows(
        test_db,
        tmp_path / "application-packets",
        tailored=_resume_data(extra_skill="Kubernetes"),
    )

    async def fake_render(resume, db):
        return b"fake-pdf", 2, "Candidate_Resume"

    monkeypatch.setattr("backend.api.routes_resumes.render_resume_pdf_bytes", fake_render)
    monkeypatch.setattr(
        "backend.automation.application_packets._extract_pdf_text",
        lambda value: "Candidate Software Engineer Experience Python APIs " * 5,
    )

    metadata = await export_application_packet(str(item.id))
    test_db.expire_all()
    refreshed = test_db.query(ApplicationQueueItem).filter(ApplicationQueueItem.id == item.id).one()
    assert refreshed.status == "needs_review"
    assert any("Kubernetes" in issue for issue in metadata["validation_issues"])
    assert any("2 pages" in issue for issue in metadata["validation_issues"])


@pytest.mark.asyncio
async def test_feed_tailor_forces_scoring_off(test_db, monkeypatch):
    test_db.add(Setting(key="job_feeds_persona_prompt", value="Prompt {resume_json} {job_description}"))
    test_db.commit()
    captured = {}

    async def fake_tailor_impl(**kwargs):
        captured.update(kwargs)
        return "00000000-0000-0000-0000-000000000001"

    monkeypatch.setattr("backend.api.routes_resumes._tailor_impl", fake_tailor_impl)
    await _tailor_resume("persona", "00000000-0000-0000-0000-000000000002")
    assert captured["score_depth_override"] == "off"
    assert captured["allow_suggested_bullets"] is False
    assert captured["prompt_template_override"].startswith("Prompt")
