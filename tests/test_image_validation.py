"""Tests for image upload validation helper used in hero item flow."""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.views import ImageValidationError, _validate_image_upload


def _build_image_file(image_format: str = "PNG", size: tuple[int, int] = (64, 64)) -> SimpleUploadedFile:
    """Create an in-memory image file for testing."""
    buffer = BytesIO()
    image = Image.new("RGB", size, color="white")
    image.save(buffer, format=image_format)
    buffer.seek(0)
    content_type = f"image/{image_format.lower()}"
    return SimpleUploadedFile(
        name=f"test.{image_format.lower()}",
        content=buffer.read(),
        content_type=content_type,
    )


def test_validate_image_upload_accepts_valid_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A correctly sized PNG within bounds should be accepted."""
    monkeypatch.setattr("core.views.MAX_IMAGE_UPLOAD_SIZE", 1024 * 1024)
    monkeypatch.setattr("core.views.MAX_IMAGE_DIMENSION", 512)
    monkeypatch.setattr("core.views.ALLOWED_IMAGE_FORMATS", {"PNG", "JPEG"})

    uploaded_file = _build_image_file(image_format="PNG", size=(200, 200))

    # Should not raise
    _validate_image_upload(uploaded_file)


def test_validate_image_upload_rejects_too_large_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files that exceed the configured size should raise ImageValidationError."""
    uploaded_file = _build_image_file(image_format="PNG")
    monkeypatch.setattr("core.views.MAX_IMAGE_UPLOAD_SIZE", uploaded_file.size - 1)

    with pytest.raises(ImageValidationError) as exc:
        _validate_image_upload(uploaded_file)

    assert "too large" in str(exc.value).lower()


def test_validate_image_upload_rejects_unsupported_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Formats outside the allowed set should be rejected."""
    monkeypatch.setattr("core.views.ALLOWED_IMAGE_FORMATS", {"JPEG"})

    uploaded_file = _build_image_file(image_format="PNG")

    with pytest.raises(ImageValidationError) as exc:
        _validate_image_upload(uploaded_file)

    assert "unsupported" in str(exc.value).lower()


def test_validate_image_upload_rejects_large_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Images exceeding the dimension cap should raise ImageValidationError."""
    monkeypatch.setattr("core.views.MAX_IMAGE_DIMENSION", 128)

    uploaded_file = _build_image_file(image_format="PNG", size=(200, 50))

    with pytest.raises(ImageValidationError) as exc:
        _validate_image_upload(uploaded_file)

    assert "dimensions" in str(exc.value).lower()


def test_validate_image_upload_rejects_corrupted_file() -> None:
    """Corrupted files should surface the dedicated validation error."""
    corrupted = SimpleUploadedFile("broken.png", b"not-an-image", content_type="image/png")

    with pytest.raises(ImageValidationError) as exc:
        _validate_image_upload(corrupted)

    assert "corrupted" in str(exc.value).lower()
