import os
import re
import shutil
from fastapi import UploadFile

from .db import get_db_session
from .models import DBFile

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def _sanitize_name(name: str) -> str:
    """Sanitize user-provided claim number to a safe filename base."""
    # Allow alphanumerics, dot, underscore, dash; replace others with underscore
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name or "")
    # Trim leading/trailing separators; ensure non-empty
    safe = safe.strip("._-") or "claim"
    return safe


async def save_uploaded_file(file: UploadFile, claim_number: str):
    """Save uploaded file using the claim number as the filename.

    The original file extension is preserved. If a file with the same
    name already exists, a numeric suffix is appended (e.g., CLM123-1.pdf).
    Saves to the local filesystem for immediate OCR processing and also
    saves it permanently in the database (table: files).
    Returns the absolute file_path and the public URL.
    """

    # Derive extension from original filename (includes leading dot if present)
    original_name = file.filename or ""
    _, dot, ext = original_name.rpartition(".")
    extension = f".{ext}" if dot else ""

    base = _sanitize_name(claim_number)
    # Treat Swagger's default 'string' like 'claim'
    m = re.fullmatch(r"(?i)string(?:[\s._-]?(\d+))?", base)
    if m:
        digits = m.group(1)
        base = f"claim{digits}" if digits else "claim"
    # If the provided value is just digits (e.g., "1"), prefix with 'claim'
    elif re.fullmatch(r"\d+", base):
        base = f"claim{base}"
    filename = f"{base}{extension}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Avoid overwriting: add incremental suffix if needed
    if os.path.exists(file_path):
        counter = 1
        while True:
            candidate = f"{base}-{counter}{extension}"
            candidate_path = os.path.join(UPLOAD_FOLDER, candidate)
            if not os.path.exists(candidate_path):
                filename = candidate
                file_path = candidate_path
                break
            counter += 1
        counter += 1

    # Save to local filesystem for immediate OCR processing
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Read the file content and save to the database
    file.file.seek(0)
    file_content = file.file.read()

    session = get_db_session()
    try:
        db_file = DBFile(
            filename=filename,
            content=file_content,
            mime_type=file.content_type or "application/pdf"
        )
        session.merge(db_file)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

    return file_path, f"/files/{filename}"
