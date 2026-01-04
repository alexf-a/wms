"""Tests for image upload validation helper used in hero item flow."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.upload_paths import MAX_FILENAME_LENGTH, user_item_image_upload_path
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

    assert "unable to read this image file" in str(exc.value).lower()


# =============================================================================
# Upload Path Tests
# =============================================================================


def test_user_item_image_upload_path_includes_user_id() -> None:
    """Upload path should include the user ID from the item's unit owner."""
    mock_user = Mock(id=42)
    mock_unit = Mock(user=mock_user)
    mock_item = Mock(unit=mock_unit)

    path = user_item_image_upload_path(mock_item, "test.jpg")

    assert path.startswith("users/42/item_images/")


def test_user_item_image_upload_path_preserves_extension() -> None:
    """Upload path should preserve the original file extension."""
    mock_user = Mock(id=1)
    mock_unit = Mock(user=mock_user)
    mock_item = Mock(unit=mock_unit)

    path_jpg = user_item_image_upload_path(mock_item, "photo.jpg")
    path_png = user_item_image_upload_path(mock_item, "image.png")
    path_jpeg = user_item_image_upload_path(mock_item, "picture.jpeg")

    assert path_jpg.endswith(".jpg")
    assert path_png.endswith(".png")
    assert path_jpeg.endswith(".jpeg")


def test_user_item_image_upload_path_generates_unique_filenames() -> None:
    """Multiple calls with the same filename should generate unique paths."""
    mock_user = Mock(id=1)
    mock_unit = Mock(user=mock_user)
    mock_item = Mock(unit=mock_unit)

    path1 = user_item_image_upload_path(mock_item, "image.jpg")
    path2 = user_item_image_upload_path(mock_item, "image.jpg")
    path3 = user_item_image_upload_path(mock_item, "image.jpg")

    # All paths should be different due to UUID prefix
    assert path1 != path2
    assert path2 != path3
    assert path1 != path3

    # But all should end with _image.jpg
    assert path1.endswith("_image.jpg")
    assert path2.endswith("_image.jpg")
    assert path3.endswith("_image.jpg")


def test_user_item_image_upload_path_truncates_long_filenames() -> None:
    """Very long filenames should be truncated to prevent path issues."""
    mock_user = Mock(id=1)
    mock_unit = Mock(user=mock_user)
    mock_item = Mock(unit=mock_unit)

    long_filename = "a" * 100 + ".jpg"
    path = user_item_image_upload_path(mock_item, long_filename)

    # Extract just the filename part (after item_images/)
    filename_part = path.split("/")[-1]
    # Should be uuid (8 chars) + _ + truncated name (MAX_FILENAME_LENGTH) + .jpg
    # Total should be reasonable (not 100+ chars)
    assert len(filename_part) <= 8 + 1 + MAX_FILENAME_LENGTH + 4


def test_user_item_image_upload_path_handles_complex_filenames() -> None:
    """Filenames with spaces and special characters should be handled safely."""
    mock_user = Mock(id=1)
    mock_unit = Mock(user=mock_user)
    mock_item = Mock(unit=mock_unit)

    path = user_item_image_upload_path(mock_item, "my photo (2024).jpg")

    # Should still generate a valid path
    assert path.startswith("users/1/item_images/")
    assert path.endswith(".jpg")
    assert "_my photo (2024).jpg" in path
