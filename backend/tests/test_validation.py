import pytest
from fastapi import HTTPException

from app.validation import validate_fields, validate_file_magic


def test_title_too_long_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_fields(
            title="x" * 201,
            description="ok",
            category="payment",
            severity_hint="high",
            reporter_email="a@b.com",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["field"] == "title"  # ty: ignore[invalid-argument-type]


def test_description_too_long_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_fields(
            title="ok",
            description="x" * 5001,
            category="payment",
            severity_hint="high",
            reporter_email="a@b.com",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["field"] == "description"  # ty: ignore[invalid-argument-type]


def test_invalid_category_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_fields(
            title="ok",
            description="ok",
            category="bogus",
            severity_hint="high",
            reporter_email="a@b.com",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["field"] == "category"  # ty: ignore[invalid-argument-type]


def test_invalid_email_raises_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_fields(
            title="ok",
            description="ok",
            category="payment",
            severity_hint="high",
            reporter_email="notanemail",
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["field"] == "reporter_email"  # ty: ignore[invalid-argument-type]


def test_valid_fields_pass():
    validate_fields(
        title="ok",
        description="ok",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )


def test_png_magic_bytes_accepted():
    content = b"\x89PNG\r\n\x1a\nrest"
    result = validate_file_magic(content, "screenshot.png")
    assert result == "image"


def test_jpg_magic_bytes_accepted():
    content = b"\xff\xd8\xff\xe0rest"
    result = validate_file_magic(content, "photo.jpg")
    assert result == "image"


def test_invalid_magic_bytes_raises_415():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_magic(b"JUNK_DATA_HERE", "fake.png")
    assert exc_info.value.status_code == 415


def test_wav_magic_bytes_accepted():
    content = b"RIFF\x00\x00\x00\x00WAVErest"
    result = validate_file_magic(content, "recording.wav")
    assert result == "audio"


def test_text_log_accepted():
    content = b"2024-01-01 ERROR something failed\nline2"
    result = validate_file_magic(content, "app.log")
    assert result == "log_file"


def test_oversized_image_raises_413():
    with pytest.raises(HTTPException) as exc_info:
        validate_file_magic(b"\x89PNG" + b"\x00" * (10 * 1024 * 1024 + 1), "big.png")
    assert exc_info.value.status_code == 413
