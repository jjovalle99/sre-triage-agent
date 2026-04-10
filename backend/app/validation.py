import re
from typing import Never

from fastapi import HTTPException

from app.models import Category, SeverityHint

_EMAIL_RE = re.compile(r".+@.+\..+")

_IMAGE_MAGIC = [
    (b"\x89PNG", "image"),
    (b"\xff\xd8\xff", "image"),
]

_AUDIO_MAGIC = [
    (b"RIFF", "audio"),
    (b"\xff\xfb", "audio"),
    (b"\xff\xf3", "audio"),
    (b"\xff\xf2", "audio"),
    (b"ID3", "audio"),
    (b"\x1aE\xdf\xa3", "audio"),
    (b"OggS", "audio"),
    (b"fLaC", "audio"),
]

_MP4_EXTENSIONS = frozenset((".mp4", ".m4a", ".m4b", ".aac"))

_MAX_IMAGE_SIZE = 10 * 1024 * 1024
_MAX_LOG_SIZE = 5 * 1024 * 1024
_MAX_AUDIO_SIZE = 25 * 1024 * 1024

_VALID_CATEGORIES = frozenset(c.value for c in Category)
_VALID_SEVERITIES = frozenset(s.value for s in SeverityHint)


def _raise(status: int, field: str, msg: str) -> Never:
    raise HTTPException(status_code=status, detail={"field": field, "error": msg})


def validate_fields(
    *,
    title: str,
    description: str,
    category: str,
    severity_hint: str,
    reporter_email: str,
) -> None:
    if len(title) > 200:
        _raise(400, "title", "Title must be 200 characters or fewer")
    if not title.strip():
        _raise(400, "title", "Title is required")
    if len(description) > 5000:
        _raise(400, "description", "Description must be 5000 characters or fewer")
    if not description.strip():
        _raise(400, "description", "Description is required")

    if category not in _VALID_CATEGORIES:
        _raise(400, "category", f"Category must be one of: {', '.join(sorted(_VALID_CATEGORIES))}")

    if severity_hint not in _VALID_SEVERITIES:
        _raise(400, "severity_hint", f"Severity must be one of: {', '.join(sorted(_VALID_SEVERITIES))}")

    if reporter_email and not _EMAIL_RE.match(reporter_email):
        _raise(400, "reporter_email", "Invalid email format")


def validate_file_magic(content: bytes, filename: str) -> str:
    """Validate file content via magic bytes. Returns file type or raises."""
    for prefix, file_type in _IMAGE_MAGIC:
        if content[:len(prefix)] == prefix:
            if len(content) > _MAX_IMAGE_SIZE:
                _raise(413, "file", f"Image exceeds {_MAX_IMAGE_SIZE // (1024 * 1024)}MB limit")
            return file_type

    for prefix, file_type in _AUDIO_MAGIC:
        if content[:len(prefix)] == prefix:
            if len(content) > _MAX_AUDIO_SIZE:
                _raise(413, "file", f"Audio exceeds {_MAX_AUDIO_SIZE // (1024 * 1024)}MB limit")
            return file_type

    if content[4:8] == b"ftyp" and filename.lower().endswith(tuple(_MP4_EXTENSIONS)):
        if len(content) > _MAX_AUDIO_SIZE:
            _raise(413, "file", f"Audio exceeds {_MAX_AUDIO_SIZE // (1024 * 1024)}MB limit")
        return "audio"

    if filename.lower().endswith((".txt", ".log")):
        try:
            content[:1024].decode("utf-8")
        except UnicodeDecodeError:
            _raise(415, "file", "Log file must be valid UTF-8 text")
        if len(content) > _MAX_LOG_SIZE:
            _raise(413, "file", f"Log file exceeds {_MAX_LOG_SIZE // (1024 * 1024)}MB limit")
        return "log_file"

    _raise(415, "file", f"Unsupported file type for '{filename}'")
