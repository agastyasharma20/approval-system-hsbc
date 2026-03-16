from __future__ import annotations
import uuid
import mimetypes
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.config import settings

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


async def save_upload(file: UploadFile, req_ref: str) -> dict:
    name = file.filename or "file"
    ext  = Path(name).suffix.lstrip(".").lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(400, f"File type .{ext} not allowed")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, f"File too large (max {settings.MAX_UPLOAD_MB} MB)")

    mime = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    stored = f"{req_ref}_{uuid.uuid4().hex}.{ext}"
    dest   = settings.upload_path / req_ref
    dest.mkdir(parents=True, exist_ok=True)
    (dest / stored).write_bytes(content)

    return {
        "filename":    name,
        "stored_name": stored,
        "file_path":   str(dest / stored),
        "file_size":   len(content),
        "mime_type":   mime,
    }
