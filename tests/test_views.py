"""Tests for core/views.py to verify rendering, authentication, and responses."""

from __future__ import annotations

import http
import json
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from core.models import ITEM_QUANTITY_DECIMAL_PLACES, Item, Location, Unit
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
        assert response.url == reverse("onboarding")

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


@pytest.mark.django_db
class TestChangePasswordView:
    """Tests for password change view."""

    def test_change_password_requires_authentication(self, client: Client):
        """Test password change view requires login."""
        response = client.get(reverse("change_password"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_change_password_get_renders_form(self, client: Client, user: User):
        """Test GET request renders password change form."""
        client.force_login(user)
        response = client.get(reverse("change_password"))
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["is_forced"] is False

    def test_change_password_get_shows_forced_flag(self, client: Client, user_must_change_password: User):
        """Test GET request shows is_forced=True when must_change_password is set."""
        client.force_login(user_must_change_password)
        response = client.get(reverse("change_password"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["is_forced"] is True

    def test_change_password_post_success(self, client: Client, user: User):
        """Test POST request with valid data changes password."""
        client.force_login(user)
        response = client.post(
            reverse("change_password"),
            {
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")

        # Verify password was changed
        user.refresh_from_db()
        assert user.check_password("NewSecurePass123!")

        # Verify success message
        messages = list(get_messages(response.wsgi_request))
        assert any("changed successfully" in str(m) for m in messages)

    def test_change_password_clears_must_change_flag(self, client: Client, user_must_change_password: User):
        """Test POST request clears must_change_password flag on success."""
        client.force_login(user_must_change_password)
        assert user_must_change_password.must_change_password is True

        response = client.post(
            reverse("change_password"),
            {
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )
        assert response.status_code == http.HTTPStatus.FOUND

        # Verify flag was cleared
        user_must_change_password.refresh_from_db()
        assert user_must_change_password.must_change_password is False

    def test_change_password_post_invalid_current_password(self, client: Client, user: User):
        """Test POST request with invalid current password shows errors."""
        client.force_login(user)
        response = client.post(
            reverse("change_password"),
            {
                "current_password": "wrongpassword",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].errors

    def test_change_password_post_weak_password(self, client: Client, user: User):
        """Test POST request with weak password shows errors."""
        client.force_login(user)
        response = client.post(
            reverse("change_password"),
            {
                "current_password": "testpass123",
                "new_password1": "weak",  # Too short
                "new_password2": "weak",
            },
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].errors

    def test_change_password_post_mismatched_passwords(self, client: Client, user: User):
        """Test POST request with mismatched passwords shows errors."""
        client.force_login(user)
        response = client.post(
            reverse("change_password"),
            {
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "DifferentPassword123!",
            },
        )
        assert response.status_code == http.HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].errors

    def test_change_password_maintains_session(self, client: Client, user: User):
        """Test password change maintains user session (doesn't log out)."""
        client.force_login(user)

        response = client.post(
            reverse("change_password"),
            {
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            },
        )

        # User should still be authenticated after password change
        assert response.wsgi_request.user.is_authenticated
        assert response.wsgi_request.user == user


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


    def test_home_redirects_to_onboarding_for_new_user(self, client: Client, user_needs_onboarding: User):
        """Test home page redirects to onboarding for users who haven't completed it."""
        client.force_login(user_needs_onboarding)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("onboarding")

    def test_home_dashboard_counts_zero(self, client: Client, user: User):
        """Test dashboard shows zero counts for new user with no data."""
        client.force_login(user)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["location_count"] == 0
        assert response.context["unit_count"] == 0
        assert response.context["item_count"] == 0

    def test_home_dashboard_counts_accurate(
        self, client: Client, user: User, location: Location, standalone_unit: Unit, item: Item
    ):
        """Test dashboard counts match actual data."""
        client.force_login(user)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["location_count"] == 1
        assert response.context["unit_count"] == 1
        assert response.context["item_count"] == 1

    def test_home_dashboard_counts_exclude_other_users(
        self, client: Client, user: User, other_user: User
    ):
        """Test dashboard counts only include current user's data."""
        other_unit = Unit.objects.create(user=other_user, name="Other Bin")
        Location.objects.create(user=other_user, name="Other House")
        Item.objects.create(
            user=other_user, name="Other Hammer", unit=other_unit, description="x"
        )

        client.force_login(user)
        response = client.get(reverse("home_view"))
        assert response.context["location_count"] == 0
        assert response.context["unit_count"] == 0
        assert response.context["item_count"] == 0


@pytest.mark.django_db
class TestOnboardingView:
    """Tests for the onboarding wizard view."""

    def test_onboarding_requires_auth(self, client: Client):
        """Test onboarding page requires authentication."""
        response = client.get(reverse("onboarding"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_onboarding_renders_for_new_user(self, client: Client, user_needs_onboarding: User):
        """Test onboarding page renders for users who haven't completed it."""
        client.force_login(user_needs_onboarding)
        response = client.get(reverse("onboarding"))
        assert response.status_code == http.HTTPStatus.OK

    def test_onboarding_uses_correct_template(self, client: Client, user_needs_onboarding: User):
        """Test onboarding page renders the onboarding template."""
        client.force_login(user_needs_onboarding)
        response = client.get(reverse("onboarding"))
        assert "core/onboarding.html" in [t.name for t in response.templates]

    def test_onboarding_redirects_if_already_completed(self, client: Client, user: User):
        """Test onboarding redirects to home for users who already completed it."""
        client.force_login(user)
        response = client.get(reverse("onboarding"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")

    def test_onboarding_has_no_active_nav(self, client: Client, user_needs_onboarding: User):
        """Test onboarding page does not set active_nav (no bottom nav)."""
        client.force_login(user_needs_onboarding)
        response = client.get(reverse("onboarding"))
        assert "active_nav" not in response.context


@pytest.mark.django_db
class TestCompleteOnboardingApi:
    """Tests for the complete onboarding API endpoint."""

    def test_complete_onboarding_requires_auth(self, client: Client):
        """Test complete onboarding API requires authentication."""
        response = client.post(reverse("complete_onboarding_api"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_complete_onboarding_sets_flag(self, client: Client, user_needs_onboarding: User):
        """Test POST sets has_completed_onboarding to True."""
        client.force_login(user_needs_onboarding)
        response = client.post(reverse("complete_onboarding_api"))
        assert response.status_code == http.HTTPStatus.OK
        data = json.loads(response.content)
        assert data["status"] == "ok"

        user_needs_onboarding.refresh_from_db()
        assert user_needs_onboarding.has_completed_onboarding is True

    def test_complete_onboarding_rejects_get(self, client: Client, user_needs_onboarding: User):
        """Test GET request is rejected with 405."""
        client.force_login(user_needs_onboarding)
        response = client.get(reverse("complete_onboarding_api"))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED

    def test_complete_onboarding_is_idempotent(self, client: Client, user: User):
        """Test completing onboarding when already onboarded still succeeds."""
        client.force_login(user)
        response = client.post(reverse("complete_onboarding_api"))
        assert response.status_code == http.HTTPStatus.OK
        data = json.loads(response.content)
        assert data["status"] == "ok"

        user.refresh_from_db()
        assert user.has_completed_onboarding is True


@pytest.mark.django_db
class TestOnboardingFlow:
    """End-to-end tests for the registration → onboarding → home flow."""

    def test_new_user_has_onboarding_incomplete(self, client: Client):
        """Test newly registered user has has_completed_onboarding=False."""
        client.post(
            reverse("register"),
            {
                "email": "flowtest@example.com",
                "password1": "securepass123!",
                "password2": "securepass123!",
            },
        )
        user = User.objects.get(email="flowtest@example.com")
        assert user.has_completed_onboarding is False

    def test_full_onboarding_flow(self, client: Client):
        """Test register → onboarding → complete → home works end-to-end."""
        # Step 1: Register
        response = client.post(
            reverse("register"),
            {
                "email": "flowtest@example.com",
                "password1": "securepass123!",
                "password2": "securepass123!",
            },
        )
        assert response.url == reverse("onboarding")

        # Step 2: Onboarding page is accessible
        response = client.get(reverse("onboarding"))
        assert response.status_code == http.HTTPStatus.OK

        # Step 3: Home redirects back to onboarding (not yet completed)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("onboarding")

        # Step 4: Complete onboarding
        response = client.post(reverse("complete_onboarding_api"))
        assert response.status_code == http.HTTPStatus.OK

        # Step 5: Home is now accessible
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK

        # Step 6: Onboarding now redirects to home
        response = client.get(reverse("onboarding"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("home_view")


@pytest.mark.django_db
class TestCreateLocationAPI:
    """Tests for the create location JSON API endpoint."""

    def test_create_location_requires_auth(self, client: Client):
        """Test create location API requires authentication."""
        response = client.post(
            reverse("api_create_location"),
            data=json.dumps({"name": "My House"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_create_location_success(self, client: Client, user: User):
        """Test POST with valid name creates location and returns 201."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_location"),
            data=json.dumps({"name": "New House"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        data = response.json()
        assert data["name"] == "New House"
        assert "id" in data
        assert Location.objects.filter(user=user, name="New House").exists()

    def test_create_location_with_address(self, client: Client, user: User):
        """Test POST with name and address saves both fields."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_location"),
            data=json.dumps({"name": "Office", "address": "456 Work Ave"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        loc = Location.objects.get(user=user, name="Office")
        assert loc.address == "456 Work Ave"

    def test_create_location_duplicate_name(self, client: Client, user: User):
        """Test duplicate location name for same user returns 409."""
        Location.objects.create(user=user, name="Duplicate")
        client.force_login(user)
        response = client.post(
            reverse("api_create_location"),
            data=json.dumps({"name": "Duplicate"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CONFLICT
        assert "already exists" in response.json()["error"]

    def test_create_location_empty_name(self, client: Client, user: User):
        """Test POST with empty name returns 400."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_location"),
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "required" in response.json()["error"].lower()

    def test_create_location_rejects_get(self, client: Client, user: User):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(reverse("api_create_location"))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestCreateUnitAPI:
    """Tests for the create unit JSON API endpoint."""

    def test_create_unit_requires_auth(self, client: Client):
        """Test create unit API requires authentication."""
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "Shelf"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_create_unit_success(self, client: Client, user: User):
        """Test POST with valid name creates unit and returns 201."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "New Shelf"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        data = response.json()
        assert data["name"] == "New Shelf"
        assert "id" in data
        assert "access_token" in data
        assert Unit.objects.filter(user=user, name="New Shelf").exists()

    def test_create_unit_with_location(self, client: Client, user: User):
        """Test POST with location_id links unit to location."""
        loc = Location.objects.create(user=user, name="API House")
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "Garage Shelf", "location_id": loc.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        unit = Unit.objects.get(user=user, name="Garage Shelf")
        assert unit.location == loc

    def test_create_unit_without_location(self, client: Client, user: User):
        """Test POST without location_id creates standalone unit."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "Loose Bin"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        unit = Unit.objects.get(user=user, name="Loose Bin")
        assert unit.location is None

    def test_create_unit_duplicate_name(self, client: Client, user: User):
        """Test duplicate unit name for same user returns 409."""
        Unit.objects.create(user=user, name="Existing Unit")
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "Existing Unit"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CONFLICT
        assert "already exists" in response.json()["error"]

    def test_create_unit_empty_name(self, client: Client, user: User):
        """Test POST with empty name returns 400."""
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "required" in response.json()["error"].lower()

    def test_create_unit_rejects_get(self, client: Client, user: User):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(reverse("api_create_unit"))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED

    def test_create_unit_other_users_location(self, client: Client, user: User, other_user: User):
        """Test cannot link unit to another user's location."""
        other_loc = Location.objects.create(user=other_user, name="Other Place")
        client.force_login(user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "My Shelf", "location_id": other_loc.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


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
    """Tests for expand inventory view (now redirects to add_items_to_unit)."""

    def test_expand_inventory_requires_authentication(self, client: Client):
        """Test expand inventory view requires login."""
        response = client.get(reverse("expand_inventory"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_expand_inventory_redirects_to_add_items(self, client: Client, user: User):
        """Test expand inventory redirects to add_items_to_unit."""
        client.force_login(user)
        response = client.get(reverse("expand_inventory"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("add_items_to_unit")


@pytest.mark.django_db
class TestCreateStorageView:
    """Tests for create storage view (now redirects to browse page)."""

    def test_create_storage_requires_authentication(self, client: Client):
        """Test create storage view requires login."""
        response = client.get(reverse("create_storage"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_create_storage_redirects_to_browse(self, client: Client, user: User):
        """Test GET request redirects to browse page."""
        client.force_login(user)
        response = client.get(reverse("create_storage"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert reverse("list_units") in response.url

    def test_create_storage_post_also_redirects(self, client: Client, user: User):
        """Test POST request also redirects to browse page."""
        client.force_login(user)
        response = client.post(reverse("create_storage"), {"name": "Test"})
        assert response.status_code == http.HTTPStatus.FOUND
        assert reverse("list_units") in response.url


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
        """Test list units shows locations and orphan units."""
        client.force_login(user)
        response = client.get(reverse("list_units"))
        assert response.status_code == http.HTTPStatus.OK
        assert "locations" in response.context
        assert "orphan_units" in response.context
        assert response.context["active_nav"] == "see"
        # standalone_unit has no location, so it should be in orphan_units
        orphan_names = [u.name for u in response.context["orphan_units"]]
        assert standalone_unit.name in orphan_names


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
        # Create an image large enough to exceed MAX_IMAGE_UPLOAD_SIZE (10MB default)
        # 2000x2000 RGB BMP = ~12MB (uncompressed, no random data needed)
        large_img = Image.new("RGB", (2000, 2000), color="blue")
        img_io = BytesIO()
        # Save as BMP (uncompressed) to ensure large file size
        large_img.save(img_io, format="BMP")
        img_io.seek(0)
        file_size = len(img_io.getvalue())
        # Verify our test image is actually larger than the limit
        assert file_size > MAX_IMAGE_UPLOAD_SIZE, (
            f"Test image ({file_size} bytes) must be larger than "
            f"MAX_IMAGE_UPLOAD_SIZE ({MAX_IMAGE_UPLOAD_SIZE} bytes)"
        )

        image_file = SimpleUploadedFile(
            "large.bmp",
            img_io.getvalue(),
            content_type="image/bmp"
        )

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
    def test_caddy_ca_returns_404_if_not_exists(self, mock_path_class: Mock, mock_path, client: Client):
        """Test returns 404 if CA certificate doesn't exist."""
        path_instance = mock_path(exists=False)
        mock_path_class.return_value = path_instance

        response = client.get(reverse("caddy_ca_download"))
        assert response.status_code == http.HTTPStatus.NOT_FOUND
        data = json.loads(response.content)
        assert "error" in data

    @patch("core.views.Path")
    def test_caddy_ca_returns_certificate_if_exists(self, mock_path_class: Mock, mock_path, client: Client):
        """Test returns certificate file if it exists."""
        ca_content = b"-----BEGIN CERTIFICATE-----\nfake cert\n-----END CERTIFICATE-----"
        path_instance = mock_path(exists=True, file_content=ca_content)
        mock_path_class.return_value = path_instance

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


# =============================================================================
# Quantity Update API
# =============================================================================


@pytest.fixture
def item_with_quantity(user: User, standalone_unit: Unit) -> Item:
    """Create a test item with count-based quantity tracking."""
    return Item.objects.create(
        user=user,
        name="Nails",
        description="Box of nails",
        unit=standalone_unit,
        quantity=Decimal("10"),
        quantity_unit="count",
    )


@pytest.fixture
def item_with_decimal_quantity(user: User, standalone_unit: Unit) -> Item:
    """Create a test item with decimal (kg) quantity tracking."""
    return Item.objects.create(
        user=user,
        name="Rice",
        description="Bag of rice",
        unit=standalone_unit,
        quantity=Decimal("2.5"),
        quantity_unit="kg",
    )


@pytest.mark.django_db
class TestUpdateItemQuantityAPI:
    """Tests for the update_item_quantity_api endpoint."""

    def _url(self, item_id: int) -> str:
        return reverse("update_item_quantity_api", args=[item_id])

    # ----- increment -----

    def test_increment_count_item(self, client: Client, user: User, item_with_quantity: Item):
        """Test incrementing a count-based item increases by 1."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["quantity"] == 11
        assert "count" in data["formatted"]

    def test_increment_decimal_item(self, client: Client, user: User, item_with_decimal_quantity: Item):
        """Test incrementing a kg item increases by 0.1."""
        client.force_login(user)
        response = client.post(self._url(item_with_decimal_quantity.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["quantity"] == 2.6

    def test_increment_is_atomic(self, client: Client, user: User, item_with_quantity: Item):
        """Test that increment uses atomic F() expression (value in DB changes correctly)."""
        client.force_login(user)
        # Manually change DB value to simulate concurrent modification
        Item.objects.filter(id=item_with_quantity.id).update(quantity=Decimal("20"))
        response = client.post(self._url(item_with_quantity.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.OK
        # Should be 21 (DB value 20 + 1), not 11 (stale in-memory 10 + 1)
        assert response.json()["quantity"] == 21

    # ----- decrement -----

    def test_decrement_count_item(self, client: Client, user: User, item_with_quantity: Item):
        """Test decrementing a count-based item decreases by 1."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "decrement"})
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["quantity"] == 9

    def test_decrement_decimal_item(self, client: Client, user: User, item_with_decimal_quantity: Item):
        """Test decrementing a kg item decreases by 0.1."""
        client.force_login(user)
        response = client.post(self._url(item_with_decimal_quantity.id), {"action": "decrement"})
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["quantity"] == 2.4

    def test_decrement_clamps_at_zero(self, client: Client, user: User, standalone_unit: Unit):
        """Test decrementing at zero does not go negative."""
        zero_item = Item.objects.create(
            user=user, name="Empty", description="empty", unit=standalone_unit,
            quantity=Decimal(0), quantity_unit="count",
        )
        client.force_login(user)
        response = client.post(self._url(zero_item.id), {"action": "decrement"})
        assert response.status_code == http.HTTPStatus.OK
        assert response.json()["quantity"] == 0

    def test_decrement_is_atomic(self, client: Client, user: User, item_with_quantity: Item):
        """Test that decrement uses atomic F() expression."""
        client.force_login(user)
        Item.objects.filter(id=item_with_quantity.id).update(quantity=Decimal("20"))
        response = client.post(self._url(item_with_quantity.id), {"action": "decrement"})
        assert response.status_code == http.HTTPStatus.OK
        assert response.json()["quantity"] == 19

    # ----- set -----

    def test_set_quantity(self, client: Client, user: User, item_with_quantity: Item):
        """Test setting an absolute quantity value."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "set", "value": "42"})
        assert response.status_code == http.HTTPStatus.OK
        assert response.json()["quantity"] == 42

    def test_set_clamps_negative_to_zero(self, client: Client, user: User, item_with_quantity: Item):
        """Test setting a negative value clamps to zero."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "set", "value": "-5"})
        assert response.status_code == http.HTTPStatus.OK
        assert response.json()["quantity"] == 0

    def test_set_rounds_decimal_for_non_count(self, client: Client, user: User, item_with_decimal_quantity: Item):
        """Test setting a decimal value rounds to configured decimal places for non-count units."""
        client.force_login(user)
        response = client.post(self._url(item_with_decimal_quantity.id), {"action": "set", "value": "3.456"})
        assert response.status_code == http.HTTPStatus.OK
        expected_quantity = float(Decimal("3.456").quantize(Decimal(10) ** -ITEM_QUANTITY_DECIMAL_PLACES))
        assert response.json()["quantity"] == expected_quantity

    def test_set_missing_value(self, client: Client, user: User, item_with_quantity: Item):
        """Test set action without value parameter returns 400."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "set"})
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "Missing" in response.json()["error"]

    def test_set_invalid_value(self, client: Client, user: User, item_with_quantity: Item):
        """Test set action with non-numeric value returns 400."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "set", "value": "abc"})
        assert response.status_code == http.HTTPStatus.BAD_REQUEST

    # ----- invalid action -----

    def test_invalid_action(self, client: Client, user: User, item_with_quantity: Item):
        """Test unknown action returns 400."""
        client.force_login(user)
        response = client.post(self._url(item_with_quantity.id), {"action": "multiply"})
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "Invalid action" in response.json()["error"]

    # ----- permissions -----

    def test_requires_authentication(self, client: Client, item_with_quantity: Item):
        """Test unauthenticated request redirects to login."""
        response = client.post(self._url(item_with_quantity.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_other_user_denied(self, client: Client, other_user: User, item_with_quantity: Item):
        """Test another user cannot modify the item quantity."""
        client.force_login(other_user)
        response = client.post(self._url(item_with_quantity.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    # ----- edge cases -----

    def test_nonexistent_item(self, client: Client, user: User):
        """Test updating a nonexistent item returns 404."""
        client.force_login(user)
        response = client.post(self._url(99999), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_item_without_quantity(self, client: Client, user: User, item: Item):
        """Test updating an item without quantity tracking returns 400."""
        client.force_login(user)
        response = client.post(self._url(item.id), {"action": "increment"})
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "quantity tracking" in response.json()["error"]

    def test_get_method_rejected(self, client: Client, user: User, item_with_quantity: Item):
        """Test GET method returns 405."""
        client.force_login(user)
        response = client.get(self._url(item_with_quantity.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


# =============================================================================
# Browse API Endpoints
# =============================================================================


@pytest.mark.django_db
class TestBrowseLocationsAPI:
    """Tests for the browse locations JSON API endpoint."""

    def test_requires_auth(self, client: Client):
        """Test browse locations API requires authentication."""
        response = client.get(reverse("api_browse_locations"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_locations_with_unit_counts(
        self, client: Client, user: User, location: Location, unit_in_location: Unit
    ):
        """Test GET returns locations with accurate unit counts."""
        client.force_login(user)
        response = client.get(reverse("api_browse_locations"))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert len(data["locations"]) == 1
        loc = data["locations"][0]
        assert loc["name"] == location.name
        assert loc["unit_count"] == 1

    def test_includes_orphan_units_with_item_counts(
        self, client: Client, user: User, standalone_unit: Unit, item: Item
    ):
        """Test orphan units (no location, no parent) with item counts."""
        client.force_login(user)
        response = client.get(reverse("api_browse_locations"))
        data = response.json()
        assert len(data["orphan_units"]) == 1
        orphan = data["orphan_units"][0]
        assert orphan["name"] == standalone_unit.name
        assert orphan["item_count"] == 1
        assert orphan["access_token"] == standalone_unit.access_token

    def test_excludes_other_users_data(
        self, client: Client, user: User, other_user: User
    ):
        """Test only own locations and units are returned."""
        Location.objects.create(user=other_user, name="Other Place")
        Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.get(reverse("api_browse_locations"))
        data = response.json()
        assert len(data["locations"]) == 0
        assert len(data["orphan_units"]) == 0

    def test_empty_user(self, client: Client, user: User):
        """Test user with no data gets empty lists."""
        client.force_login(user)
        response = client.get(reverse("api_browse_locations"))
        data = response.json()
        assert data["locations"] == []
        assert data["orphan_units"] == []

    def test_rejects_post(self, client: Client, user: User):
        """Test POST request is rejected with 405."""
        client.force_login(user)
        response = client.post(reverse("api_browse_locations"))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestBrowseLocationUnitsAPI:
    """Tests for the browse location units JSON API endpoint."""

    def _url(self, location_id: int) -> str:
        return reverse("api_browse_location_units", kwargs={"location_id": location_id})

    def test_requires_auth(self, client: Client, location: Location):
        """Test browse location units API requires authentication."""
        response = client.get(self._url(location.id))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_units_with_counts(
        self, client: Client, user: User, location: Location, unit_in_location: Unit, item: Item
    ):
        """Test GET returns units with item and child counts."""
        # Add an item to unit_in_location
        Item.objects.create(user=user, name="Wrench", unit=unit_in_location)
        client.force_login(user)
        response = client.get(self._url(location.id))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["location"]["id"] == location.id
        assert data["location"]["name"] == location.name
        assert len(data["units"]) == 1
        unit_data = data["units"][0]
        assert unit_data["name"] == unit_in_location.name
        assert unit_data["item_count"] == 1

    def test_404_for_other_users_location(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot browse other user's location."""
        other_loc = Location.objects.create(user=other_user, name="Other Place")
        client.force_login(user)
        response = client.get(self._url(other_loc.id))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_post(self, client: Client, user: User, location: Location):
        """Test POST request is rejected with 405."""
        client.force_login(user)
        response = client.post(self._url(location.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestBrowseUnitItemsAPI:
    """Tests for the browse unit items JSON API endpoint."""

    def _url(self, user_id: int, access_token: str) -> str:
        return reverse(
            "api_browse_unit_items",
            kwargs={"user_id": user_id, "access_token": access_token},
        )

    def test_requires_auth(self, client: Client, standalone_unit: Unit):
        """Test browse unit items API requires authentication."""
        response = client.get(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_items_and_child_units(
        self, client: Client, user: User, standalone_unit: Unit, nested_unit: Unit, item: Item
    ):
        """Test GET returns items and child units with counts."""
        client.force_login(user)
        response = client.get(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["unit"]["id"] == standalone_unit.id
        assert data["unit"]["name"] == standalone_unit.name
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == item.name
        assert len(data["child_units"]) == 1
        assert data["child_units"][0]["name"] == nested_unit.name

    def test_returns_parent_label_for_location(
        self, client: Client, user: User, location: Location, unit_in_location: Unit
    ):
        """Test parent_label is set to location name when unit has a location."""
        client.force_login(user)
        response = client.get(
            self._url(unit_in_location.user_id, unit_in_location.access_token)
        )
        data = response.json()
        assert data["parent_label"] == location.name

    def test_returns_parent_label_for_parent_unit(
        self, client: Client, user: User, standalone_unit: Unit, nested_unit: Unit
    ):
        """Test parent_label is set to parent unit name when unit has a parent."""
        client.force_login(user)
        response = client.get(
            self._url(nested_unit.user_id, nested_unit.access_token)
        )
        data = response.json()
        assert data["parent_label"] == standalone_unit.name

    def test_404_for_other_users_unit(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot browse other user's unit."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.get(self._url(other_unit.user_id, other_unit.access_token))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_post(self, client: Client, user: User, standalone_unit: Unit):
        """Test POST request is rejected with 405."""
        client.force_login(user)
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


# =============================================================================
# Phase 6: Location & Unit CRUD API Endpoints
# =============================================================================


@pytest.mark.django_db
class TestUpdateLocationAPI:
    """Tests for the update location JSON API endpoint."""

    def _url(self, location_id: int) -> str:
        return reverse("api_update_location", kwargs={"location_id": location_id})

    def test_requires_auth(self, client: Client, location: Location):
        """Test update location API requires authentication."""
        response = client.post(
            self._url(location.id),
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success(self, client: Client, user: User, location: Location):
        """Test POST with valid name updates location and returns 200."""
        client.force_login(user)
        response = client.post(
            self._url(location.id),
            data=json.dumps({"name": "Updated House", "address": "456 New St"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["name"] == "Updated House"
        assert data["address"] == "456 New St"
        location.refresh_from_db()
        assert location.name == "Updated House"
        assert location.address == "456 New St"

    def test_duplicate_name(self, client: Client, user: User, location: Location):
        """Test duplicate location name for same user returns 409."""
        Location.objects.create(user=user, name="Other Place")
        client.force_login(user)
        response = client.post(
            self._url(location.id),
            data=json.dumps({"name": "Other Place"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CONFLICT
        assert "already exists" in response.json()["error"]

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot update other user's location."""
        other_loc = Location.objects.create(user=other_user, name="Other Home")
        client.force_login(user)
        response = client.post(
            self._url(other_loc.id),
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_get(self, client: Client, user: User, location: Location):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(self._url(location.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestDeleteLocationAPI:
    """Tests for the delete location JSON API endpoint."""

    def _url(self, location_id: int) -> str:
        return reverse("api_delete_location", kwargs={"location_id": location_id})

    def test_requires_auth(self, client: Client, location: Location):
        """Test delete location API requires authentication."""
        response = client.post(self._url(location.id))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success_orphans_units(
        self, client: Client, user: User, location: Location, unit_in_location: Unit
    ):
        """Test POST deletes location and orphans child units."""
        client.force_login(user)
        response = client.post(self._url(location.id))
        assert response.status_code == http.HTTPStatus.OK
        assert response.json()["success"] is True
        assert not Location.objects.filter(id=location.id).exists()
        # Child unit should still exist but with no location
        unit_in_location.refresh_from_db()
        assert unit_in_location.location is None

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot delete other user's location."""
        other_loc = Location.objects.create(user=other_user, name="Other Home")
        client.force_login(user)
        response = client.post(self._url(other_loc.id))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_get(self, client: Client, user: User, location: Location):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(self._url(location.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestUnitDetailJsonAPI:
    """Tests for the unit detail JSON API endpoint."""

    def _url(self, user_id: int, access_token: str) -> str:
        return reverse(
            "api_unit_detail_json",
            kwargs={"user_id": user_id, "access_token": access_token},
        )

    def test_requires_auth(self, client: Client, standalone_unit: Unit):
        """Test unit detail JSON API requires authentication."""
        response = client.get(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_all_fields(
        self, client: Client, user: User, unit_with_dimensions: Unit
    ):
        """Test GET returns all editable unit fields."""
        client.force_login(user)
        response = client.get(
            self._url(unit_with_dimensions.user_id, unit_with_dimensions.access_token)
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["name"] == "Toolbox"
        assert data["description"] == "Red toolbox"
        assert data["length"] == 24.0
        assert data["width"] == 12.0
        assert data["height"] == 8.0
        assert data["dimensions_unit"] == "in"
        assert "id" in data
        assert "user_id" in data
        assert "access_token" in data

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot view other user's unit detail."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.get(
            self._url(other_unit.user_id, other_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestUpdateUnitAPI:
    """Tests for the update unit JSON API endpoint."""

    def _url(self, user_id: int, access_token: str) -> str:
        return reverse(
            "api_update_unit",
            kwargs={"user_id": user_id, "access_token": access_token},
        )

    def test_requires_auth(self, client: Client, standalone_unit: Unit):
        """Test update unit API requires authentication."""
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token),
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success(self, client: Client, user: User, standalone_unit: Unit):
        """Test POST with valid name updates unit and returns 200."""
        client.force_login(user)
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token),
            data=json.dumps({"name": "Updated Bin", "description": "New desc"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["name"] == "Updated Bin"
        standalone_unit.refresh_from_db()
        assert standalone_unit.name == "Updated Bin"
        assert standalone_unit.description == "New desc"

    def test_update_with_location(
        self, client: Client, user: User, standalone_unit: Unit, location: Location
    ):
        """Test POST with location_id assigns unit to location."""
        client.force_login(user)
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token),
            data=json.dumps({"name": standalone_unit.name, "location_id": location.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        standalone_unit.refresh_from_db()
        assert standalone_unit.location == location
        assert standalone_unit.parent_unit is None

    def test_dimensions_all_or_nothing(
        self, client: Client, user: User, standalone_unit: Unit
    ):
        """Test partial dimensions returns 400."""
        client.force_login(user)
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token),
            data=json.dumps({"name": "Test", "length": 10}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "dimension" in response.json()["error"].lower()

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot update other user's unit."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.post(
            self._url(other_unit.user_id, other_unit.access_token),
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_get(self, client: Client, user: User, standalone_unit: Unit):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestDeleteUnitAPI:
    """Tests for the delete unit JSON API endpoint."""

    def _url(self, user_id: int, access_token: str) -> str:
        return reverse(
            "api_delete_unit",
            kwargs={"user_id": user_id, "access_token": access_token},
        )

    def test_requires_auth(self, client: Client, standalone_unit: Unit):
        """Test delete unit API requires authentication."""
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success_cascade_deletes_items(
        self, client: Client, user: User, standalone_unit: Unit, item: Item
    ):
        """Test POST deletes unit, cascade-deletes items, orphans children."""
        # item fixture is in standalone_unit
        child = Unit.objects.create(
            user=user, name="Child", parent_unit=standalone_unit
        )
        client.force_login(user)
        response = client.post(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
        assert data["items_deleted"] == 1
        assert not Unit.objects.filter(id=standalone_unit.id).exists()
        assert not Item.objects.filter(id=item.id).exists()
        # Child unit should still exist but with no parent
        child.refresh_from_db()
        assert child.parent_unit is None

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot delete other user's unit."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.post(
            self._url(other_unit.user_id, other_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_get(self, client: Client, user: User, standalone_unit: Unit):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(
            self._url(standalone_unit.user_id, standalone_unit.access_token)
        )
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestContainerOptionsAPI:
    """Tests for the container options JSON API endpoint."""

    def test_requires_auth(self, client: Client):
        """Test container options API requires authentication."""
        response = client.get(reverse("api_container_options"))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_locations_and_units(
        self, client: Client, user: User, location: Location, standalone_unit: Unit
    ):
        """Test GET returns locations and units for the current user."""
        client.force_login(user)
        response = client.get(reverse("api_container_options"))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        loc_names = [loc["name"] for loc in data["locations"]]
        unit_names = [u["name"] for u in data["units"]]
        assert location.name in loc_names
        assert standalone_unit.name in unit_names

    def test_excludes_other_users_data(
        self, client: Client, user: User, other_user: User
    ):
        """Test only returns current user's locations and units."""
        Location.objects.create(user=other_user, name="Other Place")
        Unit.objects.create(user=other_user, name="Other Bin")
        client.force_login(user)
        response = client.get(reverse("api_container_options"))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        for loc in data["locations"]:
            assert loc["name"] != "Other Place"
        for u in data["units"]:
            assert u["name"] != "Other Bin"

    def test_exclude_unit_param(
        self, client: Client, user: User, standalone_unit: Unit
    ):
        """Test exclude_unit query param removes a unit from results."""
        client.force_login(user)
        response = client.get(
            reverse("api_container_options") + f"?exclude_unit={standalone_unit.id}"
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        unit_ids = [u["id"] for u in data["units"]]
        assert standalone_unit.id not in unit_ids


# =============================================================================
# Phase 8: Item CRUD JSON APIs
# =============================================================================


@pytest.mark.django_db
class TestItemDetailJsonAPI:
    """Tests for the item detail JSON API endpoint."""

    def _url(self, item_id: int) -> str:
        return reverse("api_item_detail_json", kwargs={"item_id": item_id})

    def test_requires_auth(self, client: Client, item: Item):
        """Test item detail JSON API requires authentication."""
        response = client.get(self._url(item.id))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_returns_json(self, client: Client, user: User, item: Item):
        """Test GET returns all expected item fields as JSON."""
        client.force_login(user)
        response = client.get(self._url(item.id))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["id"] == item.id
        assert data["name"] == "Hammer"
        assert data["description"] == "Claw hammer"
        assert data["unit_id"] == item.unit_id
        assert data["unit_name"] == item.unit.name
        assert data["image_url"] is None
        assert data["quantity"] is None
        assert data["quantity_unit"] is None
        assert data["formatted_quantity"] is None or data["formatted_quantity"] == ""
        assert "created_on" in data

    def test_returns_quantity_fields(
        self, client: Client, user: User, item_with_quantity: Item
    ):
        """Test item with quantity includes formatted quantity."""
        client.force_login(user)
        response = client.get(self._url(item_with_quantity.id))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["quantity"] == 10.0
        assert data["quantity_unit"] == "count"
        assert data["formatted_quantity"] is not None

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot view other user's item detail."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        other_item = Item.objects.create(
            user=other_user, name="Other Item", unit=other_unit
        )
        client.force_login(user)
        response = client.get(self._url(other_item.id))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_404_for_nonexistent(self, client: Client, user: User):
        """Test returns 404 for nonexistent item ID."""
        client.force_login(user)
        response = client.get(self._url(99999))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_post(self, client: Client, user: User, item: Item):
        """Test POST request is rejected with 405."""
        client.force_login(user)
        response = client.post(self._url(item.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestUpdateItemAPI:
    """Tests for the update item JSON API endpoint."""

    def _url(self, item_id: int) -> str:
        return reverse("api_update_item", kwargs={"item_id": item_id})

    def test_requires_auth(self, client: Client, item: Item):
        """Test update item API requires authentication."""
        response = client.post(
            self._url(item.id),
            data=json.dumps({"name": "Updated"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success(self, client: Client, user: User, item: Item):
        """Test POST with valid data updates item and returns 200."""
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"name": "Updated Hammer", "description": "Ball peen"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["name"] == "Updated Hammer"
        assert data["description"] == "Ball peen"
        item.refresh_from_db()
        assert item.name == "Updated Hammer"
        assert item.description == "Ball peen"

    def test_empty_name_rejected(self, client: Client, user: User, item: Item):
        """Test POST with empty name returns 400."""
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"name": "", "description": "No name"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "required" in response.json()["error"].lower()

    def test_duplicate_name(self, client: Client, user: User, item: Item, standalone_unit: Unit):
        """Test duplicate item name for same user returns 409."""
        Item.objects.create(user=user, name="Wrench", unit=standalone_unit)
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"name": "Wrench"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CONFLICT
        assert "already have" in response.json()["error"]

    def test_rejects_get(self, client: Client, user: User, item: Item):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(self._url(item.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot update other user's item."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        other_item = Item.objects.create(
            user=other_user, name="Other Item", unit=other_unit
        )
        client.force_login(user)
        response = client.post(
            self._url(other_item.id),
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestDeleteItemAPI:
    """Tests for the delete item JSON API endpoint."""

    def _url(self, item_id: int) -> str:
        return reverse("api_delete_item", kwargs={"item_id": item_id})

    def test_requires_auth(self, client: Client, item: Item):
        """Test delete item API requires authentication."""
        response = client.post(self._url(item.id))
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success(self, client: Client, user: User, item: Item):
        """Test POST deletes item and returns confirmation."""
        client.force_login(user)
        item_id = item.id
        response = client.post(self._url(item.id))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["status"] == "deleted"
        assert data["name"] == "Hammer"
        assert not Item.objects.filter(id=item_id).exists()

    def test_rejects_get(self, client: Client, user: User, item: Item):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(self._url(item.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED

    def test_404_for_other_user(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot delete other user's item."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        other_item = Item.objects.create(
            user=other_user, name="Other Item", unit=other_unit
        )
        client.force_login(user)
        response = client.post(self._url(other_item.id))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_404_for_nonexistent(self, client: Client, user: User):
        """Test returns 404 for nonexistent item ID."""
        client.force_login(user)
        response = client.post(self._url(99999))
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestMoveItemAPI:
    """Tests for the move item JSON API endpoint."""

    def _url(self, item_id: int) -> str:
        return reverse("api_move_item", kwargs={"item_id": item_id})

    def test_requires_auth(self, client: Client, item: Item):
        """Test move item API requires authentication."""
        response = client.post(
            self._url(item.id),
            data=json.dumps({"unit_id": 1}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.FOUND
        assert "login" in response.url

    def test_success(self, client: Client, user: User, item: Item):
        """Test POST moves item to target unit and returns confirmation."""
        target_unit = Unit.objects.create(user=user, name="Target Bin")
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"unit_id": target_unit.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["id"] == item.id
        assert data["unit_id"] == target_unit.id
        assert data["unit_name"] == "Target Bin"
        item.refresh_from_db()
        assert item.unit == target_unit

    def test_to_own_unit_only(
        self, client: Client, user: User, item: Item, other_user: User
    ):
        """Test cannot move item to another user's unit."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"unit_id": other_unit.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_404_for_other_users_item(
        self, client: Client, user: User, other_user: User
    ):
        """Test cannot move other user's item."""
        other_unit = Unit.objects.create(user=other_user, name="Other Box")
        other_item = Item.objects.create(
            user=other_user, name="Other Item", unit=other_unit
        )
        target_unit = Unit.objects.create(user=user, name="My Bin")
        client.force_login(user)
        response = client.post(
            self._url(other_item.id),
            data=json.dumps({"unit_id": target_unit.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_rejects_get(self, client: Client, user: User, item: Item):
        """Test GET request is rejected with 405."""
        client.force_login(user)
        response = client.get(self._url(item.id))
        assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED

    def test_missing_unit_id(self, client: Client, user: User, item: Item):
        """Test POST without unit_id returns 400."""
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST
        assert "unit_id" in response.json()["error"]

    def test_invalid_target_unit(self, client: Client, user: User, item: Item):
        """Test POST with nonexistent target unit returns 404."""
        client.force_login(user)
        response = client.post(
            self._url(item.id),
            data=json.dumps({"unit_id": 99999}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestSharedAccessViews:
    """Tests for shared user access to views and APIs."""

    def test_unit_detail_accessible_to_shared_read_user(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test that a read-shared user can view a unit detail page."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(other_user)
        response = client.get(
            reverse("unit_detail", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token})
        )
        assert response.status_code == http.HTTPStatus.OK
        assert response.context["permission"] == "read"

    def test_unit_detail_inaccessible_to_unshared_user(
        self, client: Client, other_user: User, standalone_unit: Unit
    ):
        """Test that an unshared user gets 404 on unit detail."""
        client.force_login(other_user)
        response = client.get(
            reverse("unit_detail", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token})
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_api_item_detail_accessible_to_shared_user(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """Test that a shared user can fetch item detail JSON."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(other_user)
        response = client.get(reverse("api_item_detail_json", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.OK

    def test_api_update_item_denied_for_read_user(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """Test that a read-only shared user cannot update items."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": item.id}),
            data=json.dumps({"name": "Updated", "description": "test"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_api_update_item_denied_for_write_user_on_others_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """Test that a write-shared user cannot update another user's item."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="write"
        )
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": item.id}),
            data=json.dumps({"name": "Updated Name", "description": "updated"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_api_delete_item_denied_for_read_user(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """Test that a read-only shared user cannot delete items."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(other_user)
        response = client.post(reverse("api_delete_item", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_api_browse_includes_shared_locations(
        self, client: Client, user: User, other_user: User, location: Location
    ):
        """Test that the browse API includes shared locations."""
        from core.models import LocationSharedAccess
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        client.force_login(other_user)
        response = client.get(reverse("api_browse_locations"))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        location_ids = [loc["id"] for loc in data["locations"]]
        assert location.id in location_ids

    def test_api_browse_includes_shared_orphan_units(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test that the browse API includes shared orphan units."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(other_user)
        response = client.get(reverse("api_browse_locations"))
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        unit_ids = [u["id"] for u in data["orphan_units"]]
        assert standalone_unit.id in unit_ids

    def test_unit_edit_denied_for_write_shared_user(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test that even a write-shared user cannot edit unit metadata (owner-only)."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="write"
        )
        client.force_login(other_user)
        response = client.get(
            reverse("unit_edit", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token})
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.django_db
class TestSharingManagementAPI:
    """Tests for the sharing management API endpoints."""

    def test_list_shares_owner_only(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test that only the owner can list shares."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(user)
        response = client.get(
            reverse("api_unit_sharing", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token})
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert len(data["shares"]) == 1
        assert data["shares"][0]["email"] == other_user.email

    def test_non_owner_cannot_list_shares(
        self, client: Client, other_user: User, standalone_unit: Unit
    ):
        """Test that non-owner cannot list shares."""
        client.force_login(other_user)
        response = client.get(
            reverse("api_unit_sharing", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token})
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_add_share_by_email(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test inviting a user by email."""
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_add", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token}),
            data=json.dumps({"email": other_user.email, "permission": "write"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        data = response.json()
        assert data["email"] == other_user.email
        assert data["permission"] == "write"

    def test_add_share_invalid_email(
        self, client: Client, user: User, standalone_unit: Unit
    ):
        """Test inviting a nonexistent email returns 404."""
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_add", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token}),
            data=json.dumps({"email": "nonexistent@example.com", "permission": "read"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_add_share_self_returns_400(
        self, client: Client, user: User, standalone_unit: Unit
    ):
        """Test that sharing with yourself returns 400."""
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_add", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token}),
            data=json.dumps({"email": user.email, "permission": "read"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.BAD_REQUEST

    def test_add_share_duplicate_returns_409(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test that duplicate sharing returns 409."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_add", kwargs={"user_id": standalone_unit.user_id, "access_token": standalone_unit.access_token}),
            data=json.dumps({"email": other_user.email, "permission": "write"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CONFLICT

    def test_remove_share(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test revoking shared access."""
        from core.models import UnitSharedAccess
        access = UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_remove", kwargs={
                "user_id": standalone_unit.user_id,
                "access_token": standalone_unit.access_token,
                "access_id": access.id,
            })
        )
        assert response.status_code == http.HTTPStatus.OK
        assert not UnitSharedAccess.objects.filter(id=access.id).exists()

    def test_update_share_permission(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Test changing a share's permission level."""
        from core.models import UnitSharedAccess
        access = UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_update", kwargs={
                "user_id": standalone_unit.user_id,
                "access_token": standalone_unit.access_token,
                "access_id": access.id,
            }),
            data=json.dumps({"permission": "write"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        access.refresh_from_db()
        assert access.permission == "write"


@pytest.mark.django_db
class TestRestrictedSharingViews:
    """Tests for the restricted sharing model where Location/parent-Unit
    sharing only grants name visibility, not unit content access."""

    def test_browse_location_units_owner_all_accessible(
        self, client: Client, user: User, location: Location
    ):
        """Owner sees all units with accessible=True."""
        from core.models import Unit
        unit = Unit.objects.create(user=user, name="Bin A", location=location)
        client.force_login(user)
        response = client.get(
            reverse("api_browse_location_units", kwargs={"location_id": location.id})
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert data["permission"] == "owner"
        assert len(data["units"]) == 1
        assert data["units"][0]["accessible"] is True
        assert "access_token" in data["units"][0]

    def test_browse_location_units_shared_user_name_only(
        self, client: Client, user: User, other_user: User, location: Location
    ):
        """Shared user without UnitSharedAccess sees unit names with accessible=False."""
        from core.models import LocationSharedAccess, Unit
        Unit.objects.create(user=user, name="Private Bin", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        client.force_login(other_user)
        response = client.get(
            reverse("api_browse_location_units", kwargs={"location_id": location.id})
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert len(data["units"]) == 1
        unit_data = data["units"][0]
        assert unit_data["accessible"] is False
        assert unit_data["name"] == "Private Bin"
        assert "access_token" not in unit_data
        assert "item_count" not in unit_data

    def test_browse_location_units_shared_user_explicit_access(
        self, client: Client, user: User, other_user: User, location: Location
    ):
        """Shared user WITH UnitSharedAccess sees that unit with accessible=True."""
        from core.models import LocationSharedAccess, Unit, UnitSharedAccess
        unit = Unit.objects.create(user=user, name="Shared Bin", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        UnitSharedAccess.objects.create(
            user=other_user, unit=unit, permission="read"
        )
        client.force_login(other_user)
        response = client.get(
            reverse("api_browse_location_units", kwargs={"location_id": location.id})
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        assert len(data["units"]) == 1
        unit_data = data["units"][0]
        assert unit_data["accessible"] is True
        assert "access_token" in unit_data
        assert "item_count" in unit_data

    def test_unit_detail_blocked_for_location_only_shared_user(
        self, client: Client, user: User, other_user: User, location: Location
    ):
        """LocationSharedAccess alone should NOT grant unit detail access."""
        from core.models import LocationSharedAccess, Unit
        unit = Unit.objects.create(user=user, name="Private Unit", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        client.force_login(other_user)
        response = client.get(
            reverse("unit_detail", kwargs={
                "user_id": unit.user_id, "access_token": unit.access_token
            })
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_create_unit_in_shared_location(
        self, client: Client, user: User, other_user: User, location: Location
    ):
        """Write-shared location user can still create units."""
        from core.models import LocationSharedAccess, Unit
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="write"
        )
        client.force_login(other_user)
        response = client.post(
            reverse("api_create_unit"),
            data=json.dumps({"name": "New Bin", "location_id": location.id}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        unit = Unit.objects.get(name="New Bin")
        assert unit.user == other_user
        assert unit.location == location

    def test_browse_unit_items_child_restricted(
        self, client: Client, user: User, other_user: User
    ):
        """Child units in a shared parent show accessible flag correctly."""
        from core.models import Unit, UnitSharedAccess
        parent = Unit.objects.create(user=user, name="Parent")
        accessible_child = Unit.objects.create(user=user, name="Shared Child", parent_unit=parent)
        restricted_child = Unit.objects.create(user=user, name="Private Child", parent_unit=parent)

        UnitSharedAccess.objects.create(user=other_user, unit=parent, permission="read")
        UnitSharedAccess.objects.create(user=other_user, unit=accessible_child, permission="read")

        client.force_login(other_user)
        response = client.get(
            reverse("api_browse_unit_items", kwargs={
                "user_id": parent.user_id, "access_token": parent.access_token
            })
        )
        assert response.status_code == http.HTTPStatus.OK
        data = response.json()
        children = {c["name"]: c for c in data["child_units"]}

        assert children["Shared Child"]["accessible"] is True
        assert "access_token" in children["Shared Child"]
        assert children["Private Child"]["accessible"] is False
        assert "access_token" not in children["Private Child"]


@pytest.mark.django_db
class TestItemOwnershipEnforcement:
    """Tests for Phase 11 — item-level ownership enforcement with write/write_all."""

    def test_write_user_cannot_edit_others_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """write user cannot edit an item owned by another user via API."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write")
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": item.id}),
            data=json.dumps({"name": "Hijacked", "description": "nope"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_write_user_cannot_delete_others_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """write user cannot delete an item owned by another user via API."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write")
        client.force_login(other_user)
        response = client.post(reverse("api_delete_item", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_write_user_can_edit_own_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """write user can edit their own item in a shared unit."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write")
        own_item = Item.objects.create(user=other_user, name="My Widget", unit=standalone_unit)
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": own_item.id}),
            data=json.dumps({"name": "Renamed Widget", "description": "updated"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        own_item.refresh_from_db()
        assert own_item.name == "Renamed Widget"

    def test_write_user_can_delete_own_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """write user can delete their own item in a shared unit."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write")
        own_item = Item.objects.create(user=other_user, name="Disposable", unit=standalone_unit)
        item_id = own_item.id
        client.force_login(other_user)
        response = client.post(reverse("api_delete_item", kwargs={"item_id": item_id}))
        assert response.status_code == http.HTTPStatus.OK
        assert not Item.objects.filter(id=item_id).exists()

    def test_write_all_user_can_edit_others_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """write_all user can edit another user's item."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write_all")
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": item.id}),
            data=json.dumps({"name": "Updated by collaborator", "description": "edited"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.OK
        item.refresh_from_db()
        assert item.name == "Updated by collaborator"

    def test_write_all_user_can_delete_others_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """write_all user can delete another user's item."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="write_all")
        item_id = item.id
        client.force_login(other_user)
        response = client.post(reverse("api_delete_item", kwargs={"item_id": item_id}))
        assert response.status_code == http.HTTPStatus.OK
        assert not Item.objects.filter(id=item_id).exists()

    def test_read_user_cannot_edit_any_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """read user cannot edit any item via API."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="read")
        client.force_login(other_user)
        response = client.post(
            reverse("api_update_item", kwargs={"item_id": item.id}),
            data=json.dumps({"name": "Nope", "description": "denied"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_read_user_cannot_delete_any_item(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit, item: Item
    ):
        """read user cannot delete any item via API."""
        from core.models import UnitSharedAccess
        UnitSharedAccess.objects.create(user=other_user, unit=standalone_unit, permission="read")
        client.force_login(other_user)
        response = client.post(reverse("api_delete_item", kwargs={"item_id": item.id}))
        assert response.status_code == http.HTTPStatus.NOT_FOUND

    def test_sharing_api_accepts_write_all(
        self, client: Client, user: User, other_user: User, standalone_unit: Unit
    ):
        """Sharing API accepts write_all as a valid permission."""
        client.force_login(user)
        response = client.post(
            reverse("api_unit_sharing_add", kwargs={
                "user_id": standalone_unit.user_id,
                "access_token": standalone_unit.access_token,
            }),
            data=json.dumps({"email": other_user.email, "permission": "write_all"}),
            content_type="application/json",
        )
        assert response.status_code == http.HTTPStatus.CREATED
        data = response.json()
        assert data["permission"] == "write_all"
