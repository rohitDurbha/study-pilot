"""Settings and checks that keep the public backend safe to expose.

    FRONTEND_ORIGIN    origins allowed by CORS, comma separated,
                       default "http://localhost:3000"
    MAX_UPLOAD_MB      largest request body in megabytes, default 10

Only PDF, plain text and Markdown files are accepted, and the content has to
match the extension, so a renamed binary is refused before it reaches the
document processor or a language model.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

DEFAULT_FRONTEND_ORIGIN = "http://localhost:3000"
DEFAULT_MAX_UPLOAD_MB = 10.0

PDF_EXTENSIONS = (".pdf",)
TEXT_EXTENSIONS = (".txt", ".md", ".markdown")
ALLOWED_EXTENSIONS = PDF_EXTENSIONS + TEXT_EXTENSIONS


class UploadRejected(ValueError):
    """An uploaded file has a type or content the backend does not accept."""


def allowed_origins(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """Origins from FRONTEND_ORIGIN, without blanks or trailing slashes."""
    env = os.environ if env is None else env
    raw = env.get("FRONTEND_ORIGIN", "") or DEFAULT_FRONTEND_ORIGIN
    origins = [part.strip().rstrip("/") for part in raw.split(",")]
    origins = [o for o in origins if o]
    return origins or [DEFAULT_FRONTEND_ORIGIN]


def max_upload_bytes(env: Optional[Mapping[str, str]] = None) -> int:
    """Largest request body in bytes, from MAX_UPLOAD_MB."""
    env = os.environ if env is None else env
    raw = (env.get("MAX_UPLOAD_MB") or "").strip()
    try:
        megabytes = float(raw) if raw else DEFAULT_MAX_UPLOAD_MB
    except ValueError as exc:
        raise ValueError(f"MAX_UPLOAD_MB must be a number, got {raw!r}") from exc
    if megabytes <= 0:
        raise ValueError(f"MAX_UPLOAD_MB must be above zero, got {raw!r}")
    return int(megabytes * 1024 * 1024)


def classify_upload(filename: str, data: bytes) -> str:
    """Return "pdf" or "text" for an accepted file, or raise UploadRejected."""
    name = (filename or "").lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise UploadRejected(f"Only {allowed} files can be uploaded.")

    if name.endswith(PDF_EXTENSIONS):
        if not data.lstrip()[:5].startswith(b"%PDF-"):
            raise UploadRejected("The file ends in .pdf but is not a PDF document.")
        return "pdf"

    if b"\x00" in data:
        raise UploadRejected("The file looks like binary data, not plain text or Markdown.")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadRejected("Text and Markdown files must be UTF-8 encoded.") from exc
    return "text"
