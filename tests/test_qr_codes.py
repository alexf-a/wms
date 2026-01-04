"""Tests for QR code generation helpers and views."""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from core.models import Unit, UnitSharedAccess, WMSUser
from core.utils import generate_unit_access_token, get_qr_code_file


def test_generate_unit_access_token_produces_unique_urlsafe_tokens() -> None:
    """Token generator should return unique, URL-safe strings."""
    samples = {generate_unit_access_token() for _ in range(100)}

    assert len(samples) == 100
    assert all(isinstance(token, str) for token in samples)
    assert all("/" not in token and "+" not in token for token in samples)
    assert all(len(token) >= 22 for token in samples)


def test_get_qr_code_file_wraps_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The QR code helper should serialize the generated image to a ContentFile."""

    class DummyQR:
        def save(self, buffer, format):  # noqa: D401, ANN001 - qrcode interface
            buffer.write(b"fake-qr")

    mocked_qr = DummyQR()

    with mock.patch("core.utils.get_qr_code", return_value=mocked_qr) as mocked_make:
        content_file = get_qr_code_file("https://example.com/unit", filename="example.png")

    mocked_make.assert_called_once_with("https://example.com/unit")
    assert isinstance(content_file, ContentFile)
    assert content_file.name == "example.png"
    assert content_file.read() == b"fake-qr"


@pytest.mark.django_db
def test_get_qr_filename_slugifies_unit_name() -> None:
    """Unit QR filenames should slugify the unit name and add a suffix."""
    user = WMSUser.objects.create_user(email="owner@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=user, name="Exercise Equipment", description="desc")

    assert storage_unit.get_qr_filename() == "exercise-equipment_unit_qr.png"


@pytest.mark.django_db
def test_get_qr_filename_falls_back_when_slug_empty() -> None:
    """Units with names that slugify to empty should use the default filename."""
    user = WMSUser.objects.create_user(email="owner2@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=user, name="!!!", description="desc")

    assert storage_unit.get_qr_filename() == "unit_unit_qr.png"


@pytest.mark.django_db
def test_get_detail_path_matches_reverse() -> None:
    """Detail path should match the named URL reversal."""
    user = WMSUser.objects.create_user(email="owner3@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=user, name="Garage", description="desc")

    expected_path = reverse(
        "unit_detail", kwargs={"user_id": user.id, "access_token": storage_unit.access_token}
    )
    assert storage_unit.get_detail_path() == expected_path


@pytest.mark.django_db
def test_get_qr_code_joins_base_url_and_detail_path() -> None:
    """Unit.get_qr_code should call helper with the fully-qualified detail URL."""
    user = WMSUser.objects.create_user(email="owner4@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=user, name="Basement", description="desc")

    fake_file = ContentFile(b"qr-bytes", name="basement_qr.png")
    with mock.patch("core.models.get_qr_code_file", return_value=fake_file) as mocked_helper:
        result = storage_unit.get_qr_code(base_url="https://example.com/app")

    mocked_helper.assert_called_once()
    helper_args, helper_kwargs = mocked_helper.call_args
    assert helper_args[0] == "https://example.com/app" + storage_unit.get_detail_path()
    assert helper_kwargs["filename"] == storage_unit.get_qr_filename()
    assert result is fake_file


@pytest.mark.django_db
def test_unit_qr_view_allows_owner(client) -> None:
    """The unit owner should be able to download their QR code."""
    user = WMSUser.objects.create_user(email="owner5@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=user, name="Pantry", description="desc")
    client.force_login(user)

    fake_file = ContentFile(b"qr-content", name="pantry_qr.png")
    with mock.patch.object(Unit, "get_qr_code", return_value=fake_file) as mocked_get_qr:
        url = reverse("unit_qr", args=(user.id, storage_unit.access_token))
        response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["Content-Disposition"] == 'attachment; filename="pantry_qr.png"'
    mocked_get_qr.assert_called_once_with(base_url="http://testserver/")


@pytest.mark.django_db
def test_unit_qr_view_allows_shared_user(client) -> None:
    """Users with shared access should be able to download the QR code."""
    owner = WMSUser.objects.create_user(email="owner6@example.com", password="pass123")
    shared_user = WMSUser.objects.create_user(email="shared@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=owner, name="Office", description="desc")
    UnitSharedAccess.objects.create(unit=storage_unit, user=shared_user, permission="read")
    client.force_login(shared_user)

    fake_file = ContentFile(b"qr-content", name="office_qr.png")
    with mock.patch.object(Unit, "get_qr_code", return_value=fake_file):
        url = reverse("unit_qr", args=(owner.id, storage_unit.access_token))
        response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Disposition"] == 'attachment; filename="office_qr.png"'


@pytest.mark.django_db
def test_unit_qr_view_denies_unrelated_user(client) -> None:
    """Unrelated users should receive a 404 when requesting a QR code."""
    owner = WMSUser.objects.create_user(email="owner7@example.com", password="pass123")
    other_user = WMSUser.objects.create_user(email="other@example.com", password="pass123")
    storage_unit = Unit.objects.create(user=owner, name="Attic", description="desc")
    client.force_login(other_user)

    url = reverse("unit_qr", args=(owner.id, storage_unit.access_token))
    response = client.get(url)

    assert response.status_code == 404
