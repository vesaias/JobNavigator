"""CV PDF upload and download endpoints."""
import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
import pdfplumber

from backend.models.db import get_db, CV

router = APIRouter(prefix="/cvs", tags=["cvs"])

MAX_CVS = 9


@router.get("")
def list_cvs(db: Session = Depends(get_db)):
    """List all uploaded CVs (metadata only)."""
    cvs = db.query(CV).order_by(CV.uploaded_at).all()
    return [
        {
            "id": str(cv.id),
            "version": cv.version,
            "filename": cv.filename,
            "page_count": cv.page_count,
            "extracted_text_preview": cv.extracted_text[:300] if cv.extracted_text else "",
            "uploaded_at": cv.uploaded_at.isoformat() if cv.uploaded_at else None,
        }
        for cv in cvs
    ]


@router.post("/{version}")
async def upload_cv(version: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF CV for a named version (any name, 1-50 chars, max 5 CVs total)."""
    version = version.strip()
    if not version or len(version) > 50:
        raise HTTPException(status_code=400, detail="Version name must be 1-50 characters")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Check max CVs (only if this is a new version)
    existing = db.query(CV).filter(CV.version == version).first()
    if not existing:
        total = db.query(CV).count()
        if total >= MAX_CVS:
            raise HTTPException(status_code=400, detail=f"Maximum {MAX_CVS} CVs allowed. Delete one first.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF too large (max 10 MB)")

    # Extract text via pdfplumber
    extracted_text = ""
    page_count = 0
    warning = None
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to process PDF: {str(e)}")

    if len(extracted_text) < 100:
        warning = "PDF may be image-based, extraction may have failed"

    # Upsert: replace existing CV for this version
    if existing:
        existing.filename = file.filename
        existing.pdf_data = pdf_bytes
        existing.extracted_text = extracted_text
        existing.page_count = page_count
        from backend.models.db import utcnow
        existing.uploaded_at = utcnow()
    else:
        cv = CV(
            version=version,
            filename=file.filename,
            pdf_data=pdf_bytes,
            extracted_text=extracted_text,
            page_count=page_count,
        )
        db.add(cv)

    db.commit()

    result = {
        "version": version,
        "filename": file.filename,
        "page_count": page_count,
        "extracted_text_preview": extracted_text[:300] if extracted_text else "",
    }
    if warning:
        result["warning"] = warning
    return result


@router.get("/{version}")
def get_cv(version: str, db: Session = Depends(get_db)):
    """Get CV metadata and extracted text preview."""
    cv = db.query(CV).filter(CV.version == version).first()
    if not cv:
        raise HTTPException(status_code=404, detail=f"No CV uploaded for version: {version}")

    return {
        "id": str(cv.id),
        "version": cv.version,
        "filename": cv.filename,
        "page_count": cv.page_count,
        "extracted_text_preview": cv.extracted_text[:300] if cv.extracted_text else "",
        "uploaded_at": cv.uploaded_at.isoformat() if cv.uploaded_at else None,
    }


@router.get("/{version}/download")
def download_cv(version: str, db: Session = Depends(get_db)):
    """Download original PDF."""
    cv = db.query(CV).filter(CV.version == version).first()
    if not cv:
        raise HTTPException(status_code=404, detail=f"No CV uploaded for version: {version}")

    return Response(
        content=cv.pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cv.filename}"'}
    )


@router.delete("/{version}")
def delete_cv(version: str, db: Session = Depends(get_db)):
    """Delete a CV and clean up company references."""
    cv = db.query(CV).filter(CV.version == version).first()
    if not cv:
        raise HTTPException(status_code=404, detail=f"No CV uploaded for version: {version}")

    # Note: Company.selected_resume_ids holds Resume UUIDs (not CV IDs) so
    # deleting a CV no longer requires cleanup of company references.
    db.delete(cv)
    db.commit()
    return {"deleted": True, "version": version}
