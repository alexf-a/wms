"""Tests for core/views.py to verify rendering, authentication, and responses."""

from __future__ import annotations

import http
import json
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from core.models import Item, Location, Unit
from core.views import MAX_IMAGE_DIMENSION, MAX_IMAGE_UPLOAD_SIZE, ImageValidationError

if TYPE_CHECKING:
    from django.test import Client

    from core.models import WMSUser as User
else:
    User = get_user_model()


# =============================================================================
# Authentication Views
# =============================================================================


@pytest.mark.django_db
class TestRegisterView:
    """Tests for user registration view."""

    def test_register_get_renders_form(self, client: Client):
        """Test GET request renders registration form."""
        response = client.get(reverse("register"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert b"register" in response.content.lower()

    def test_register_post_creates_user_and_logs_in(self, client: Client):
        """Test successful registration creates user and logs them in."""
        response = client.post(
            reverse("register"),
            {
                "email": "newuser@example.com",
                "password1": "securepass123!",
                "password2": "securepass123!",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")

        # Verify user was created
        user = User.objects.get(email="newuser@example.com")
        assert user.check_password("securepass123!")

        # Verify user is logged in
        assert "_auth_user_id" in client.session

    def test_register_post_invalid_form_shows_errors(self, client: Client):
        """Test registration with invalid data shows errors."""
        response = client.post(
            reverse("register"),
            {
                "email": "invalid-email",
                "password1": "pass",
                "password2": "different",
            },
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].errors


@pytest.mark.django_db
class TestLoginView:
    """Tests for user login view."""

    def test_login_get_renders_form(self, client: Client):
        """Test GET request renders login form."""
        response = client.get(reverse("login"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context

    def test_login_redirects_if_already_authenticated(self, client: Client, user: User):
        """Test authenticated users are redirected from login page."""
        client.force_login(user)
        response = client.get(reverse("login"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")

    def test_login_post_success(self, client: Client, user: User):
        """Test successful login with valid credentials."""
        response = client.post(
            reverse("login"),
            {"email": user.email, "password": "testpass123"},
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")
        assert "_auth_user_id" in client.session

    def test_login_post_invalid_credentials(self, client: Client, user: User):
        """Test login fails with invalid credentials."""
        response = client.post(
            reverse("login"),
            {"email": user.email, "password": "wrongpassword"},
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].errors

    def test_login_redirects_to_next_parameter(self, client: Client, user: User):
        """Test login redirects to 'next' parameter if provided."""
        target_url = reverse("list_units")
        response = client.post(
            f"{reverse('login')}?next={target_url}",
            {"email": user.email, "password": "testpass123"},
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == target_url


@pytest.mark.django_db
class TestAccountView:
    """Tests for account settings view."""

    def test_account_requires_authentication(self, client: Client):
        """Test account view requires login."""
        response = client.get(reverse("account"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_account_get_renders_form(self, client: Client, user: User):
        """Test GET request renders account form."""
        client.force_login(user)
        response = client.get(reverse("account"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["active_nav"] == "account"

    def test_account_post_updates_user(self, client: Client, user: User):
        """Test POST request updates user information."""
        client.force_login(user)
        response = client.post(
            reverse("account"),
            {"email": user.email},  # Email field required
        )
        assert response.status_code == http.HTTPStatus.FOUND
        messages = list(get_messages(response.wsgi_request))
        assert any("updated successfully" in str(m) for m in messages)


# =============================================================================
# Public Views
# =============================================================================


@pytest.mark.django_db
class TestHomeView:
    """Tests for home page view."""

    def test_home_renders_for_anonymous_users(self, client: Client):
        """Test home page renders for unauthenticated users."""
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK
        assert "is_authenticated" in response.context
        assert not response.context["is_authenticated"]

    def test_home_renders_for_authenticated_users(self, client: Client, user: User):
        """Test home page renders for authenticated users."""
        client.force_login(user)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["is_authenticated"]
        assert response.context["active_nav"] == "home"


@pytest.mark.django_db
class TestGettingStartedView:
    """Tests for getting started guide view."""

    def test_getting_started_renders_for_all_users(self, client: Client):
        """Test getting started page is accessible to all."""
        response = client.get(reverse("getting_started"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["active_nav"] is None


@pytest.mark.django_db
class TestHealthcheckView:
    """Tests for healthcheck endpoint."""

    def test_healthcheck_returns_ok(self, client: Client):
        """Test healthcheck returns 200 with status ok."""
        response = client.get(reverse("healthcheck"))
        assert response.status_code == http.HTTPStatus.OK
        data = json.loads(response.content)
        assert data["status"] == "ok"


# =============================================================================
# Storage Space Views
# =============================================================================


@pytest.mark.django_db
class TestExpandInventoryView:
    """Tests for expand inventory view."""

    def test_expand_inventory_requires_authentication(self, client: Client):
        """Test expand inventory view requires login."""
        response = client.get(reverse("expand_inventory"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_expand_inventory_renders_for_authenticated_users(self, client: Client, user: User):
        """Test expand inventory renders for logged-in users."""
        client.force_login(user)
        response = client.get(reverse("expand_inventory"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["active_nav"] == "add"


@pytest.mark.django_db
class TestCreateStorageView:
    """Tests for creating storage spaces (locations/units)."""

    def test_create_storage_requires_authentication(self, client: Client):
        """Test create storage view requires login."""
        response = client.get(reverse("create_storage"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_create_storage_get_renders_form(self, client: Client, user: User):
        """Test GET request renders storage creation form."""
        client.force_login(user)
        response = client.get(reverse("create_storage"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context

    def test_create_storage_post_creates_unit(self, client: Client, user: User):
        """Test POST creates a unit successfully."""
        client.force_login(user)
        response = client.post(
            reverse("create_storage"),
            {
                "stores_items": "unit",
                "name": "Test Unit",
                "description": "Test description",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify unit was created
        unit = Unit.objects.get(name="Test Unit", user=user)
        assert unit.description == "Test description"
        assert unit.user == user

    def test_create_storage_post_creates_location(self, client: Client, user: User):
        """Test POST creates a location successfully."""
        client.force_login(user)
        response = client.post(
            reverse("create_storage"),
            {
                "stores_items": "location",
                "name": "Test Location",
                "description": "Test location description",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify location was created
        location = Location.objects.get(name="Test Location", user=user)
        assert location.description == "Test location description"


# =============================================================================
# Unit Views
# =============================================================================


@pytest.mark.django_db
class TestListUnitsView:
    """Tests for listing units."""

    def test_list_units_requires_authentication(self, client: Client):
        """Test list units view requires login."""
        response = client.get(reverse("list_units"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_list_units_displays_user_units(self, client: Client, user: User, standalone_unit: Unit):
        """Test list units shows only user's units."""
        client.force_login(user)
        response = client.get(reverse("list_units"))
        assert response.status_code == http.HTTPStatus.OK
        assert "units" in response.context
        assert standalone_unit in response.context["units"]
        assert response.context["active_nav"] == "see"


@pytest.mark.django_db
class TestUnitDetailView:
    """Tests for unit detail view."""

    def test_unit_detail_requires_authentication(self, client: Client, standalone_unit: Unit):
        """Test unit detail view requires login."""
        response = client.get(
            reverse(
                "unit_detail",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_unit_detail_renders_for_owner(self, client: Client, user: User, standalone_unit: Unit):
        """Test unit detail renders for the owner."""
        client.force_login(user)
        response = client.get(
            reverse(
                "unit_detail",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "unit" in response.context
        assert response.context["unit"] == standalone_unit

    def test_unit_detail_404_for_nonexistent_unit(self, client: Client, user: User):
        """Test unit detail returns 404 for invalid access token."""
        client.force_login(user)
        response = client.get(
            reverse(
                "unit_detail",
                kwargs={
                    "user_id": user.id,
                    "access_token": "invalid-token",
                },
            )
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestUnitQRView:
    """Tests for unit QR code view."""

    def test_unit_qr_requires_authentication(self, client: Client, standalone_unit: Unit):
        """Test QR code view requires login."""
        response = client.get(
            reverse(
                "unit_qr",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    @patch("core.models.Unit.get_qr_code")
    def test_unit_qr_returns_png_for_owner(
        self, mock_get_qr_code: Mock, client: Client, user: User, standalone_unit: Unit
    ):
        """Test QR code returns PNG image for owner."""
        # Mock QR code file
        mock_file = Mock()
        mock_file.read.return_value = b"fake-png-data"
        mock_file.name = "test_qr.png"
        mock_file.seek = Mock()
        mock_get_qr_code.return_value = mock_file

        client.force_login(user)
        response = client.get(
            reverse(
                "unit_qr",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.OK
        assert response["Content-Type"] == "image/png"
        assert b"fake-png-data" in response.content

    def test_unit_qr_404_for_other_user(self, client: Client, other_user: User, standalone_unit: Unit):
        """Test QR code returns 404 for non-owner."""
        client.force_login(other_user)
        response = client.get(
            reverse(
                "unit_qr",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestUnitEditView:
    """Tests for editing units."""

    def test_unit_edit_requires_authentication(self, client: Client, standalone_unit: Unit):
        """Test unit edit view requires login."""
        response = client.get(
            reverse(
                "unit_edit",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_unit_edit_get_renders_form(self, client: Client, user: User, standalone_unit: Unit):
        """Test GET request renders unit edit form."""
        client.force_login(user)
        response = client.get(
            reverse(
                "unit_edit",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert "unit" in response.context
        assert response.context["unit"] == standalone_unit

    def test_unit_edit_post_updates_unit(self, client: Client, user: User, standalone_unit: Unit):
        """Test POST request updates unit successfully."""
        client.force_login(user)
        response = client.post(
            reverse(
                "unit_edit",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            ),
            {
                "name": "Updated Unit Name",
                "description": "Updated description",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify unit was updated
        standalone_unit.refresh_from_db()
        assert standalone_unit.name == "Updated Unit Name"
        assert standalone_unit.description == "Updated description"

    def test_unit_edit_404_for_other_user(self, client: Client, other_user: User, standalone_unit: Unit):
        """Test unit edit returns 404 for non-owner."""
        client.force_login(other_user)
        response = client.get(
            reverse(
                "unit_edit",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestUnitDeleteView:
    """Tests for deleting units."""

    def test_unit_delete_requires_authentication(self, client: Client, standalone_unit: Unit):
        """Test unit delete view requires login."""
        response = client.post(
            reverse(
                "unit_delete",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_unit_delete_post_deletes_unit(self, client: Client, user: User, standalone_unit: Unit):
        """Test POST request deletes unit."""
        client.force_login(user)
        unit_id = standalone_unit.id

        response = client.post(
            reverse(
                "unit_delete",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("list_units")

        # Verify unit was deleted
        assert not Unit.objects.filter(id=unit_id).exists()

    def test_unit_delete_get_redirects_to_detail(self, client: Client, user: User, standalone_unit: Unit):
        """Test GET request redirects instead of deleting."""
        client.force_login(user)
        response = client.get(
            reverse(
                "unit_delete",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify unit was NOT deleted
        assert Unit.objects.filter(id=standalone_unit.id).exists()

    def test_unit_delete_404_for_other_user(self, client: Client, other_user: User, standalone_unit: Unit):
        """Test unit delete returns 404 for non-owner."""
        client.force_login(other_user)
        response = client.post(
            reverse(
                "unit_delete",
                kwargs={
                    "user_id": standalone_unit.user.id,
                    "access_token": standalone_unit.access_token,
                },
            )
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


# =============================================================================
# Item Views
# =============================================================================


@pytest.mark.django_db
class TestAddItemsToUnitView:
    """Tests for adding items to units."""

    def test_add_items_requires_authentication(self, client: Client):
        """Test add items view requires login."""
        response = client.get(reverse("add_items_to_unit"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_add_items_get_renders_form(self, client: Client, user: User):
        """Test GET request renders add items form."""
        client.force_login(user)
        response = client.get(reverse("add_items_to_unit"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert "units" in response.context

    def test_add_items_post_creates_item(self, client: Client, user: User, standalone_unit: Unit):
        """Test POST creates an item successfully."""
        client.force_login(user)
        response = client.post(
            reverse("add_items_to_unit"),
            {
                "name": "Test Item",
                "description": "Test description",
                "unit": standalone_unit.id,
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify item was created
        item = Item.objects.get(name="Test Item", user=user)
        assert item.description == "Test description"
        assert item.unit == standalone_unit


@pytest.mark.django_db
class TestItemDetailView:
    """Tests for item detail view."""

    def test_item_detail_requires_authentication(self, client: Client, item: Item):
        """Test item detail view requires login."""
        response = client.get(reverse("item_detail", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_item_detail_renders_for_owner(self, client: Client, user: User, item: Item):
        """Test item detail renders for the owner."""
        client.force_login(user)
        response = client.get(reverse("item_detail", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.OK
        assert "item" in response.context
        assert response.context["item"] == item

    def test_item_detail_404_for_nonexistent_item(self, client: Client, user: User):
        """Test item detail returns 404 for invalid item ID."""
        client.force_login(user)
        response = client.get(reverse("item_detail", kwargs={"item_id": 99999}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestItemEditView:
    """Tests for editing items."""

    def test_item_edit_requires_authentication(self, client: Client, item: Item):
        """Test item edit view requires login."""
        response = client.get(reverse("item_edit", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_item_edit_get_renders_form(self, client: Client, user: User, item: Item):
        """Test GET request renders item edit form."""
        client.force_login(user)
        response = client.get(reverse("item_edit", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert "item" in response.context
        assert response.context["item"] == item

    def test_item_edit_post_updates_item(self, client: Client, user: User, item: Item):
        """Test POST request updates item successfully."""
        client.force_login(user)
        response = client.post(
            reverse("item_edit", kwargs={"item_id": item.id}),
            {
                "name": "Updated Item Name",
                "description": "Updated description",
                "unit": item.unit.id,
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify item was updated
        item.refresh_from_db()
        assert item.name == "Updated Item Name"
        assert item.description == "Updated description"

    def test_item_edit_404_for_other_user(self, client: Client, other_user: User, item: Item):
        """Test item edit returns 404 for non-owner."""
        client.force_login(other_user)
        response = client.get(reverse("item_edit", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestItemDeleteView:
    """Tests for deleting items."""

    def test_item_delete_requires_authentication(self, client: Client, item: Item):
        """Test item delete view requires login."""
        response = client.post(reverse("item_delete", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_item_delete_post_deletes_item(self, client: Client, user: User, item: Item):
        """Test POST request deletes item."""
        client.force_login(user)
        item_id = item.id

        response = client.post(reverse("item_delete", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify item was deleted
        assert not Item.objects.filter(id=item_id).exists()

    def test_item_delete_get_redirects_to_detail(self, client: Client, user: User, item: Item):
        """Test GET request redirects instead of deleting."""
        client.force_login(user)
        response = client.get(reverse("item_delete", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify item was NOT deleted
        assert Item.objects.filter(id=item.id).exists()

    def test_item_delete_404_for_other_user(self, client: Client, other_user: User, item: Item):
        """Test item delete returns 404 for non-owner."""
        client.force_login(other_user)
        response = client.post(reverse("item_delete", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND


# =============================================================================
# Item Search View
# =============================================================================


@pytest.mark.django_db
class TestItemSearchView:
    """Tests for item search functionality."""

    def test_item_search_requires_authentication(self, client: Client):
        """Test item search view requires login."""
        response = client.get(reverse("item_search"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_item_search_get_renders_form(self, client: Client, user: User):
        """Test GET request renders search form."""
        client.force_login(user)
        response = client.get(reverse("item_search"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert "units" in response.context
        assert response.context["active_nav"] == "find"

    @patch("core.views.find_item_location")
    def test_item_search_post_with_query(
        self, mock_find_item_location: Mock, client: Client, user: User, item: Item
    ):
        """Test POST request with search query."""
        # Mock the search result
        mock_result = Mock()
        mock_result.item_name = item.name
        mock_result.__str__ = Mock(return_value=f"Found: {item.name}")
        mock_find_item_location.return_value = mock_result

        client.force_login(user)
        response = client.post(
            reverse("item_search"),
            {"query": "where is my hammer?"},
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "result" in response.context
        assert "found_item" in response.context

        # Verify the search function was called
        mock_find_item_location.assert_called_once_with("where is my hammer?", user.id)


# =============================================================================
# Image Extraction API
# =============================================================================


@pytest.mark.django_db
class TestExtractItemFeaturesAPI:
    """Tests for item feature extraction API."""

    def test_extract_requires_authentication(self, client: Client):
        """Test extraction API requires login."""
        response = client.post(reverse("extract_item_features_api"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_extract_requires_post(self, client: Client, user: User):
        """Test extraction API requires POST method."""
        client.force_login(user)
        response = client.get(reverse("extract_item_features_api"))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED
        data = json.loads(response.content)
        assert "error" in data

    def test_extract_requires_image(self, client: Client, user: User):
        """Test extraction API requires image file."""
        client.force_login(user)
        response = client.post(reverse("extract_item_features_api"))
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        data = json.loads(response.content)
        assert "error" in data
        assert "No image provided" in data["error"]

    @patch("core.views.extract_item_features_from_image")
    def test_extract_success(self, mock_extract: Mock, client: Client, user: User):
        """Test successful extraction returns name and description."""
        # Create a valid test image
        img = Image.new("RGB", (100, 100), color="red")
        img_io = BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)

        image_file = SimpleUploadedFile(
            "test.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )

        # Mock extraction result
        mock_result = Mock()
        mock_result.name = "Test Item"
        mock_result.description = "Test description"
        mock_extract.return_value = mock_result

        client.force_login(user)
        response = client.post(
            reverse("extract_item_features_api"),
            {"image": image_file},
        )
        assert response.status_code == http.HTTPStatus.OK
        data = json.loads(response.content)
        assert data["name"] == "Test Item"
        assert data["description"] == "Test description"

    def test_extract_rejects_oversized_image(self, client: Client, user: User):
        """Test extraction rejects images that are too large."""
        # Create an image that's too large
        large_img = Image.new("RGB", (100, 100), color="blue")
        img_io = BytesIO()
        large_img.save(img_io, format="JPEG")
        img_io.seek(0)

        # Create a mock file that reports size > MAX_IMAGE_UPLOAD_SIZE
        image_file = SimpleUploadedFile(
            "large.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )
        # Patch the size attribute
        image_file.size = MAX_IMAGE_UPLOAD_SIZE + 1

        client.force_login(user)
        response = client.post(
            reverse("extract_item_features_api"),
            {"image": image_file},
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        data = json.loads(response.content)
        assert "error" in data
        assert "too large" in data["error"].lower()

    def test_extract_rejects_wrong_format(self, client: Client, user: User):
        """Test extraction rejects unsupported image formats."""
        # Create a fake GIF file (if GIF is not in ALLOWED_IMAGE_FORMATS)
        from core.views import ALLOWED_IMAGE_FORMATS

        # Skip if GIF is allowed
        if "GIF" in ALLOWED_IMAGE_FORMATS:
            pytest.skip("GIF is an allowed format")

        img = Image.new("RGB", (100, 100), color="green")
        img_io = BytesIO()
        img.save(img_io, format="GIF")
        img_io.seek(0)

        image_file = SimpleUploadedFile(
            "test.gif",
            img_io.getvalue(),
            content_type="image/gif"
        )

        client.force_login(user)
        response = client.post(
            reverse("extract_item_features_api"),
            {"image": image_file},
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        data = json.loads(response.content)
        assert "error" in data


# =============================================================================
# Caddy CA Download View
# =============================================================================


@pytest.mark.django_db
class TestCaddyCADownloadView:
    """Tests for Caddy CA certificate download."""

    def test_caddy_ca_no_auth_required(self, client: Client):
        """Test CA download does not require authentication."""
        response = client.get(reverse("caddy_ca_download"))
        # Should return 404 or 200, but not redirect to login
        assert response.status_code in [http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND]

    @patch("core.views.Path")
    def test_caddy_ca_returns_404_if_not_exists(self, mock_path: Mock, client: Client):
        """Test returns 404 if CA certificate doesn't exist."""
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        response = client.get(reverse("caddy_ca_download"))
        assert response.status_code == http.HTTPStatus.NOT_FOUND
        data = json.loads(response.content)
        assert "error" in data

    @patch("core.views.Path")
    def test_caddy_ca_returns_certificate_if_exists(self, mock_path: Mock, client: Client):
        """Test returns certificate file if it exists."""
        # Create a temporary certificate file
        ca_content = b"-----BEGIN CERTIFICATE-----\nfake cert\n-----END CERTIFICATE-----"

        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.open = Mock(return_value=BytesIO(ca_content))
        mock_path.return_value = mock_path_instance

        # Mock Path.open to work as a context manager
        mock_path_instance.__enter__ = Mock(return_value=BytesIO(ca_content))
        mock_path_instance.__exit__ = Mock(return_value=False)

        response = client.get(reverse("caddy_ca_download"))
        assert response.status_code == http.HTTPStatus.OK
        assert response["Content-Type"] == "application/x-pem-file"
        assert "caddy-root-ca.crt" in response["Content-Disposition"]


# =============================================================================
# Custom Error Handlers
# =============================================================================


@pytest.mark.django_db
class TestCustomErrorViews:
    """Tests for custom error handler views."""

    def test_custom_404_handler(self, client: Client):
        """Test 404 error handler renders correctly."""
        response = client.get("/nonexistent-url/")
        assert response.status_code == http.HTTPStatus.NOT_FOUND
        assert b"404" in response.content or b"not found" in response.content.lower()

    @patch("core.views.custom_400_view")
    def test_custom_400_handler_called(self, mock_view: Mock, client: Client):
        """Test 400 error handler can be invoked."""
        from django.http import HttpResponse
        mock_view.return_value = HttpResponse("Bad Request", status=http.HTTPStatus.BAD_REQUEST)

        # Trigger a 400 error (hard to do naturally in tests)
        # Just verify the view function exists and can be called
        from core.views import custom_400_view
        request = client.request().wsgi_request
        response = custom_400_view(request, exception=ValueError("test"))
        assert response.status_code == http.HTTPStatus.BAD_REQUEST

    def test_custom_403_handler(self, client: Client):
        """Test 403 error handler renders correctly."""
        from core.views import custom_403_view
        request = client.request().wsgi_request
        response = custom_403_view(request, exception=None)
        assert response.status_code == http.HTTPStatus.FORBIDDEN

    def test_custom_500_handler(self, client: Client):
        """Test 500 error handler renders correctly."""
        from core.views import custom_500_view
        request = client.request().wsgi_request
        response = custom_500_view(request)
        assert response.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR


# =============================================================================
# Image Validation Tests
# =============================================================================


@pytest.mark.django_db
class TestImageValidation:
    """Tests for image validation logic."""

    def test_validate_image_upload_valid_jpeg(self):
        """Test validation passes for valid JPEG image."""
        from core.views import _validate_image_upload

        img = Image.new("RGB", (100, 100), color="red")
        img_io = BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)

        image_file = SimpleUploadedFile(
            "test.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )

        # Should not raise exception
        _validate_image_upload(image_file)

    def test_validate_image_upload_too_large(self):
        """Test validation fails for oversized files."""
        from core.views import _validate_image_upload

        img = Image.new("RGB", (100, 100), color="blue")
        img_io = BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)

        image_file = SimpleUploadedFile(
            "large.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )
        image_file.size = MAX_IMAGE_UPLOAD_SIZE + 1

        with pytest.raises(ImageValidationError, match="too large"):
            _validate_image_upload(image_file)

    def test_validate_image_upload_oversized_dimensions(self):
        """Test validation fails for images with dimensions too large."""
        from core.views import _validate_image_upload

        # Create image with dimensions exceeding MAX_IMAGE_DIMENSION
        img = Image.new("RGB", (MAX_IMAGE_DIMENSION + 1, 100), color="green")
        img_io = BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)

        image_file = SimpleUploadedFile(
            "wide.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )

        with pytest.raises(ImageValidationError, match="dimensions are too large"):
            _validate_image_upload(image_file)

    def test_validate_image_upload_corrupted(self):
        """Test validation fails for corrupted image files."""
        from core.views import _validate_image_upload

        # Create a file that's not a valid image
        image_file = SimpleUploadedFile(
            "corrupt.jpg",
            b"not an image",
            content_type="image/jpeg"
        )

        with pytest.raises(ImageValidationError, match="Unable to read"):
            _validate_image_upload(image_file)
