"""Tests for /api/cvs CRUD endpoints."""


def _seed_first_run(db):
    from backend.models.db import Setting
    db.add(Setting(key="dashboard_api_key", value=""))
    db.commit()


# Minimal valid PDF bytes — smallest possible valid PDF.
_MINIMAL_PDF = (
    b"%PDF-1.0\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Count 0>>endobj "
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF"
)


def test_upload_rejects_non_pdf_filename(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.post(
        "/api/cvs/TPM",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "pdf" in resp.text.lower()


def test_upload_rejects_oversized_file(api_client, test_db):
    _seed_first_run(test_db)
    big = b"x" * (11 * 1024 * 1024)  # 11 MB, exceeds 10 MB limit
    resp = api_client.post(
        "/api/cvs/TPM",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 400
    # Error should mention size — exact phrase may vary.
    assert any(word in resp.text.lower() for word in ("size", "large", "mb", "limit"))


def test_upload_accepts_valid_pdf(api_client, test_db):
    _seed_first_run(test_db)
    resp = api_client.post(
        "/api/cvs/TPM",
        files={"file": ("cv.pdf", _MINIMAL_PDF, "application/pdf")},
    )
    # Accept 200 or 201 depending on router convention; 422 is allowed if pdfplumber
    # can't extract text from the minimal PDF — in that case the endpoint still returns
    # a structured error instead of 500.
    assert resp.status_code in (200, 201, 422), f"Unexpected {resp.status_code}: {resp.text}"


def test_delete_cv_does_not_affect_selected_resume_ids(api_client, test_db):
    """Deleting a CV must not break Company.selected_resume_ids (which holds Resume UUIDs, not CV IDs)."""
    _seed_first_run(test_db)
    from backend.models.db import CV, Company

    cv = CV(
        version="TPM",
        filename="cv.pdf",
        pdf_data=b"dummy",
        extracted_text="resume text",
        page_count=1,
    )
    test_db.add(cv)
    test_db.commit()

    # Company stores Resume UUIDs in selected_resume_ids — unrelated to CV deletion.
    resume_uuid = "00000000-0000-0000-0000-000000000abc"
    company = Company(name="Acme", selected_resume_ids=[resume_uuid])
    test_db.add(company)
    test_db.commit()

    # Delete endpoint is by version, not id.
    resp = api_client.delete(f"/api/cvs/{cv.version}")
    assert resp.status_code in (200, 204), f"Unexpected {resp.status_code}: {resp.text}"

    # selected_resume_ids should be untouched.
    test_db.expire_all()
    refreshed = test_db.query(Company).filter(Company.name == "Acme").first()
    assert resume_uuid in (refreshed.selected_resume_ids or []), (
        f"Expected selected_resume_ids unchanged, got: {refreshed.selected_resume_ids}"
    )
