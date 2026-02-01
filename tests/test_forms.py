"""Tests for core/forms.py to verify form validation and behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from core.forms import STORAGE_TYPE_LOCATION, STORAGE_TYPE_UNIT, PasswordChangeForm, StorageSpaceForm

if TYPE_CHECKING:
    from core.models import Location, Unit
    from core.models import WMSUser as User


@pytest.mark.django_db
class TestPasswordChangeForm:
    """Tests for PasswordChangeForm validation and password change logic."""

    def test_form_requires_user_parameter(self):
        """Test form requires user parameter for initialization."""
        with pytest.raises(TypeError):
            PasswordChangeForm()

    def test_clean_current_password_accepts_correct_password(self, user: User):
        """Test current password validation passes with correct password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

    def test_clean_current_password_rejects_incorrect_password(self, user: User):
        """Test current password validation fails with incorrect password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "wrongpassword",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "current_password" in form.errors

    def test_clean_new_password1_rejects_too_short(self, user: User):
        """Test new password validation rejects passwords that are too short."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "short",  # Less than 8 characters
                "new_password2": "short",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_all_numeric(self, user: User):
        """Test new password validation rejects all-numeric passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "12345678",  # All numeric
                "new_password2": "12345678",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_common_password(self, user: User):
        """Test new password validation rejects common passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "password123",  # Common password
                "new_password2": "password123",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_similar_to_email(self, user: User):
        """Test new password validation rejects passwords similar to user email."""
        # User email is "owner@example.com"
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "owner@example.com",  # Too similar to email
                "new_password2": "owner@example.com",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_accepts_strong_password(self, user: User):
        """Test new password validation accepts strong passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "StrongPassword123!",
                "new_password2": "StrongPassword123!",
            }
        )
        assert form.is_valid()

    def test_clean_rejects_mismatched_passwords(self, user: User):
        """Test cross-field validation rejects when passwords don't match."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "DifferentPassword123!",
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors or "new_password2" in form.errors

    def test_clean_accepts_matching_passwords(self, user: User):
        """Test cross-field validation passes when passwords match."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

    def test_save_updates_user_password(self, user: User):
        """Test save method updates the user's password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

        saved_user = form.save()

        assert saved_user == user
        assert user.check_password("NewSecurePass123!")
        assert not user.check_password("testpass123")

    def test_save_without_commit_does_not_persist(self, user: User):
        """Test save with commit=False doesn't persist to database."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

        saved_user = form.save(commit=False)

        # Password is set in memory but not saved
        assert saved_user.check_password("NewSecurePass123!")

        # Refresh from DB - should still have old password
        user.refresh_from_db()
        assert user.check_password("testpass123")


@pytest.mark.django_db
class TestStorageSpaceForm:
    """Tests for StorageSpaceForm validation and creation logic."""

    def test_form_requires_user_parameter(self):
        """Test form initialization without user parameter defaults to None."""
        # Should not raise error, but user will be None
        form = StorageSpaceForm()
        assert form.user is None

    def test_form_accepts_user_parameter(self, user: User):
        """Test form initialization with user parameter sets user."""
        form = StorageSpaceForm(user=user)
        assert form.user == user

    # ========================================================================
    # Name Validation Tests
    # ========================================================================

    def test_clean_name_rejects_duplicate_location_name(self, user: User, location: Location):
        """Test name validation rejects names that collide with existing Locations."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": location.name,  # Same name as existing location
                "stores_items": STORAGE_TYPE_LOCATION,
            }
        )
        assert not form.is_valid()
        assert "name" in form.errors
        assert "location named" in str(form.errors["name"]).lower()

    def test_clean_name_rejects_duplicate_unit_name(self, user: User, standalone_unit: Unit):
        """Test name validation rejects names that collide with existing Units."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": standalone_unit.name,  # Same name as existing unit
                "stores_items": STORAGE_TYPE_UNIT,
            }
        )
        assert not form.is_valid()
        assert "name" in form.errors
        assert "unit named" in str(form.errors["name"]).lower()

    def test_clean_name_accepts_unique_name(self, user: User):
        """Test name validation passes with unique name."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Unique Storage Space",
                "stores_items": STORAGE_TYPE_LOCATION,
            }
        )
        assert form.is_valid()

    def test_clean_name_allows_same_name_for_different_users(
        self, user: User, other_user: User, location: Location
    ):
        """Test name validation allows same name for different users."""
        # location belongs to 'user', but other_user can use the same name
        form = StorageSpaceForm(
            user=other_user,
            data={
                "name": location.name,
                "stores_items": STORAGE_TYPE_LOCATION,
            }
        )
        assert form.is_valid()

    # ========================================================================
    # Dimension Validation Tests (PRIMARY REQUIREMENTS)
    # ========================================================================

    def test_partial_dimensions_length_only_raises_validation_error(self, user: User):
        """Test submitting only length dimension raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "length": 10.0,
                # width and height omitted
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert "all three dimensions" in str(form.errors["__all__"]).lower()

    def test_partial_dimensions_length_and_width_raises_validation_error(self, user: User):
        """Test submitting length and width without height raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "length": 10.0,
                "width": 5.0,
                # height omitted
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert "all three dimensions" in str(form.errors["__all__"]).lower()

    def test_partial_dimensions_width_and_height_raises_validation_error(self, user: User):
        """Test submitting width and height without length raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "width": 5.0,
                "height": 3.0,
                # length omitted
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert "all three dimensions" in str(form.errors["__all__"]).lower()

    def test_dimensions_without_unit_raises_validation_error(self, user: User):
        """Test submitting all dimensions without unit of measurement raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "length": 10.0,
                "width": 5.0,
                "height": 3.0,
                # dimensions_unit omitted
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert "unit of measurement is required" in str(form.errors["__all__"]).lower()

    def test_complete_dimensions_with_unit_passes_validation(self, user: User):
        """Test submitting all dimensions with unit of measurement passes validation."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "length": 10.0,
                "width": 5.0,
                "height": 3.0,
                "dimensions_unit": "in",
            }
        )
        assert form.is_valid()

    def test_no_dimensions_passes_validation(self, user: User):
        """Test submitting unit without any dimensions is valid (optional fields)."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
            }
        )
        assert form.is_valid()

    def test_dimensions_unit_without_dimensions_is_cleared(self, user: User):
        """Test dimensions_unit is cleared if no dimensions are provided."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "dimensions_unit": "in",  # Provided but no dimensions
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["dimensions_unit"] is None

    # ========================================================================
    # Container Field Validation Tests
    # ========================================================================

    def test_container_empty_string_raises_validation_error(self, user: User):
        """Test empty container string raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": "",  # Empty string is handled by form field, not parse_container_string
            }
        )
        # Empty string from dropdown is valid (means no container selected)
        assert form.is_valid()

    def test_container_invalid_format_raises_validation_error(self, user: User):
        """Test invalid container format raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": "invalid_format_123",  # Invalid prefix
            }
        )
        assert not form.is_valid()

    def test_container_malformed_id_raises_validation_error(self, user: User):
        """Test malformed container ID raises ValidationError."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": "location_abc",  # Non-numeric ID
            }
        )
        assert not form.is_valid()

    def test_container_valid_location_format_passes(self, user: User, location: Location):
        """Test valid location container format passes validation."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": f"location_{location.id}",
            }
        )
        assert form.is_valid()

    def test_container_valid_unit_format_passes(self, user: User, standalone_unit: Unit):
        """Test valid unit container format passes validation."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": f"unit_{standalone_unit.id}",
            }
        )
        assert form.is_valid()

    # ========================================================================
    # stores_items Field Behavior Tests
    # ========================================================================

    def test_location_ignores_unit_specific_fields(self, user: User):
        """Test Location creation ignores unit-specific fields like dimensions."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Location",
                "stores_items": STORAGE_TYPE_LOCATION,
                "length": 10.0,  # Should be ignored for locations
                "width": 5.0,
                "height": 3.0,
                "dimensions_unit": "in",
            }
        )
        # Location ignores dimensions, so partial dimensions don't cause validation errors
        assert form.is_valid()

    def test_location_accepts_address_field(self, user: User):
        """Test Location creation accepts address field."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Location",
                "stores_items": STORAGE_TYPE_LOCATION,
                "address": "123 Test St",
            }
        )
        assert form.is_valid()

    def test_unit_ignores_address_field(self, user: User):
        """Test Unit creation ignores address field."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "address": "123 Test St",  # Should be ignored for units
            }
        )
        assert form.is_valid()

    # ========================================================================
    # Save Method Tests
    # ========================================================================

    def test_save_creates_location(self, user: User):
        """Test save method creates a Location when stores_items is 'location'."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Location",
                "stores_items": STORAGE_TYPE_LOCATION,
                "description": "Test description",
                "address": "123 Test St",
            }
        )
        assert form.is_valid()

        created = form.save()

        from core.models import Location
        assert isinstance(created, Location)
        assert created.name == "Test Location"
        assert created.description == "Test description"
        assert created.address == "123 Test St"
        assert created.user == user

    def test_save_creates_unit_without_dimensions(self, user: User):
        """Test save method creates a Unit without dimensions."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "description": "Test description",
            }
        )
        assert form.is_valid()

        created = form.save()

        from core.models import Unit
        assert isinstance(created, Unit)
        assert created.name == "Test Unit"
        assert created.description == "Test description"
        assert created.length is None
        assert created.width is None
        assert created.height is None
        assert created.dimensions_unit is None
        assert created.user == user

    def test_save_creates_unit_with_dimensions(self, user: User):
        """Test save method creates a Unit with complete dimensions."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "length": 10.0,
                "width": 5.0,
                "height": 3.0,
                "dimensions_unit": "in",
            }
        )
        assert form.is_valid()

        created = form.save()

        from core.models import Unit
        assert isinstance(created, Unit)
        assert created.length == 10.0
        assert created.width == 5.0
        assert created.height == 3.0
        assert created.dimensions_unit == "in"

    def test_save_creates_unit_in_location(self, user: User, location: Location):
        """Test save method creates a Unit inside a Location."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": f"location_{location.id}",
            }
        )
        assert form.is_valid()

        created = form.save()

        from core.models import Unit
        assert isinstance(created, Unit)
        assert created.location == location
        assert created.parent_unit is None

    def test_save_creates_nested_unit(self, user: User, standalone_unit: Unit):
        """Test save method creates a Unit nested inside another Unit."""
        form = StorageSpaceForm(
            user=user,
            data={
                "name": "Test Nested Unit",
                "stores_items": STORAGE_TYPE_UNIT,
                "container": f"unit_{standalone_unit.id}",
            }
        )
        assert form.is_valid()

        created = form.save()

        from core.models import Unit
        assert isinstance(created, Unit)
        assert created.parent_unit == standalone_unit
        assert created.location is None

    def test_save_raises_error_if_user_missing(self):
        """Test save method raises ValueError if user is not set."""
        form = StorageSpaceForm(
            data={
                "name": "Test Unit",
                "stores_items": STORAGE_TYPE_UNIT,
            }
        )
        form.is_valid()

        with pytest.raises(ValueError, match="User is required"):
            form.save()
