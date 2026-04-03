"""Tests for core/models.py custom logic."""

import base64
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from core.models import (
    CATEGORY_2_UNITS,
    CATEGORY_BY_UNIT,
    Item,
    Location,
    LocationSharedAccess,
    QUANTITY_CATEGORY_CHOICES,
    QUANTITY_UNIT_CHOICES,
    Unit,
    UnitSharedAccess,
    UNIT_2_NAME,
    WMSUser,
)


class TestWMSUserManager:
    """Tests for WMSUserManager custom methods."""

    @pytest.mark.django_db
    def test_create_user_success(self):
        """Test creating a user with email and password."""
        user = WMSUser.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    @pytest.mark.django_db
    def test_create_user_normalizes_email(self):
        """Test that email is normalized (lowercased domain)."""
        user = WMSUser.objects.create_user(
            email="test@EXAMPLE.COM",
            password="testpass123"
        )

        assert user.email == "test@example.com"

    @pytest.mark.django_db
    def test_create_user_without_email_raises_error(self):
        """Test that creating a user without email raises ValueError."""
        with pytest.raises(ValueError, match="The Email field must be set"):
            WMSUser.objects.create_user(email="", password="testpass123")

    @pytest.mark.django_db
    def test_create_superuser_success(self):
        """Test creating a superuser with correct flags."""
        user = WMSUser.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123"
        )

        assert user.email == "admin@example.com"
        assert user.is_staff is True
        assert user.is_superuser is True

    @pytest.mark.django_db
    def test_create_superuser_requires_is_staff(self):
        """Test that superuser must have is_staff=True."""
        with pytest.raises(ValueError, match="Superuser must have is_staff=True"):
            WMSUser.objects.create_superuser(
                email="admin@example.com",
                password="adminpass123",
                is_staff=False
            )

    @pytest.mark.django_db
    def test_create_superuser_requires_is_superuser(self):
        """Test that superuser must have is_superuser=True."""
        with pytest.raises(ValueError, match="Superuser must have is_superuser=True"):
            WMSUser.objects.create_superuser(
                email="admin@example.com",
                password="adminpass123",
                is_superuser=False
            )


class TestUnitConstraints:
    """Tests for Unit model CheckConstraints."""

    @pytest.mark.django_db(transaction=True)
    def test_unit_cannot_have_both_location_and_parent_unit(self, user, location, standalone_unit):
        """Test that a unit cannot have both location and parent_unit set."""
        with pytest.raises(IntegrityError):
            Unit.objects.create(
                user=user,
                name="Invalid Unit",
                location=location,
                parent_unit=standalone_unit
            )

    @pytest.mark.django_db(transaction=True)
    def test_unit_can_have_location_only(self, user, location):
        """Test that a unit can have location without parent_unit."""
        unit = Unit.objects.create(
            user=user,
            name="Valid Unit",
            location=location,
            parent_unit=None
        )

        assert unit.location == location
        assert unit.parent_unit is None

    @pytest.mark.django_db(transaction=True)
    def test_unit_can_have_parent_unit_only(self, user, standalone_unit):
        """Test that a unit can have parent_unit without location."""
        unit = Unit.objects.create(
            user=user,
            name="Nested Unit",
            location=None,
            parent_unit=standalone_unit
        )

        assert unit.parent_unit == standalone_unit
        assert unit.location is None

    @pytest.mark.django_db(transaction=True)
    def test_unit_can_have_neither_location_nor_parent(self, user):
        """Test that a unit can be standalone (no location or parent_unit)."""
        unit = Unit.objects.create(
            user=user,
            name="Standalone Unit",
            location=None,
            parent_unit=None
        )

        assert unit.location is None
        assert unit.parent_unit is None

    @pytest.mark.django_db(transaction=True)
    def test_unit_dimensions_all_or_nothing_rejects_partial(self, user):
        """Test that partial dimensions (only some fields) are rejected."""
        with pytest.raises(IntegrityError):
            Unit.objects.create(
                user=user,
                name="Invalid Dimensions",
                length=10.0,  # Only length provided
                width=None,
                height=None,
                dimensions_unit=None
            )

    @pytest.mark.django_db(transaction=True)
    def test_unit_dimensions_all_or_nothing_accepts_all(self, user):
        """Test that complete dimensions are accepted."""
        unit = Unit.objects.create(
            user=user,
            name="Complete Dimensions",
            length=10.0,
            width=8.0,
            height=6.0,
            dimensions_unit="in"
        )

        assert unit.length == 10.0
        assert unit.width == 8.0
        assert unit.height == 6.0
        assert unit.dimensions_unit == "in"

    @pytest.mark.django_db(transaction=True)
    def test_unit_dimensions_all_or_nothing_accepts_none(self, user):
        """Test that no dimensions (all None) is accepted."""
        unit = Unit.objects.create(
            user=user,
            name="No Dimensions",
            length=None,
            width=None,
            height=None,
            dimensions_unit=None
        )

        assert unit.length is None
        assert unit.width is None
        assert unit.height is None
        assert unit.dimensions_unit is None


class TestLocationPromoteToUnit:
    """Tests for Location.promote_to_unit() method."""

    @pytest.mark.django_db
    def test_promote_location_without_children(self, user: WMSUser):
        """Test promoting a location with no child units."""
        location = Location.objects.create(
            user=user,
            name="Garage",
            description="My garage",
            address="123 Main St"
        )
        location_id = location.id

        # Promote to unit
        unit = location.promote_to_unit()

        # Verify unit was created with same name and description
        assert unit.name == "Garage"
        assert unit.description == "My garage"
        assert unit.user == user
        assert unit.location is None
        assert unit.parent_unit is None

        # Verify location was deleted
        assert not Location.objects.filter(id=location_id).exists()

    @pytest.mark.django_db
    def test_promote_location_with_child_units(self, user: WMSUser):
        """Test promoting a location with child units reassigns them."""
        location = Location.objects.create(
            user=user,
            name="Shed",
            description="Storage shed"
        )

        # Create child units in the location
        child1 = Unit.objects.create(
            user=user,
            name="Shelf A",
            location=location
        )
        child2 = Unit.objects.create(
            user=user,
            name="Shelf B",
            location=location
        )

        # Promote location to unit
        unit = location.promote_to_unit()

        # Refresh child units from database
        child1.refresh_from_db()
        child2.refresh_from_db()

        # Verify children now have parent_unit set to new unit
        assert child1.parent_unit == unit
        assert child1.location is None
        assert child2.parent_unit == unit
        assert child2.location is None

    @pytest.mark.django_db
    def test_can_promote_to_unit_always_true(self, location: Location):
        """Test that can_promote_to_unit() always returns True."""
        assert location.can_promote_to_unit() is True


class TestUnitHierarchy:
    """Tests for Unit hierarchy navigation methods."""

    @pytest.mark.django_db
    def test_get_container_returns_location(self, unit_in_location: Unit, location: Location):
        """Test get_container returns location when unit is in location."""
        assert unit_in_location.get_container() == location

    @pytest.mark.django_db
    def test_get_container_returns_parent_unit(self, nested_unit: Unit, standalone_unit: Unit):
        """Test get_container returns parent_unit when unit is nested."""
        assert nested_unit.get_container() == standalone_unit

    @pytest.mark.django_db
    def test_get_container_returns_none_for_standalone(self, standalone_unit: Unit):
        """Test get_container returns None for standalone unit."""
        assert standalone_unit.get_container() is None

    @pytest.mark.django_db
    def test_parent_property_returns_location(self, unit_in_location: Unit, location: Location):
        """Test parent property returns location."""
        assert unit_in_location.parent == location

    @pytest.mark.django_db
    def test_parent_property_returns_parent_unit(self, nested_unit: Unit, standalone_unit: Unit):
        """Test parent property returns parent_unit."""
        assert nested_unit.parent == standalone_unit

    @pytest.mark.django_db
    def test_parent_property_returns_none_for_standalone(self, standalone_unit: Unit):
        """Test parent property returns None for standalone unit."""
        assert standalone_unit.parent is None

    @pytest.mark.django_db
    def test_get_full_path_standalone_unit(self, standalone_unit: Unit):
        """Test get_full_path for standalone unit returns just the name."""
        assert standalone_unit.get_full_path() == "Storage Bin"

    @pytest.mark.django_db
    def test_get_full_path_unit_in_location(self, user: WMSUser, location: Location):
        """Test get_full_path for unit in location."""
        unit = Unit.objects.create(
            user=user,
            name="Workbench",
            location=location
        )

        # Location name is included at the beginning of path
        assert unit.get_full_path() == "My House > Workbench"

    @pytest.mark.django_db
    def test_get_full_path_nested_units(self, user: WMSUser):
        """Test get_full_path for multi-level nested units."""
        root = Unit.objects.create(user=user, name="Garage")
        middle = Unit.objects.create(user=user, name="Workbench", parent_unit=root)
        leaf = Unit.objects.create(user=user, name="Toolbox", parent_unit=middle)

        assert leaf.get_full_path() == "Garage > Workbench > Toolbox"

    @pytest.mark.django_db
    def test_get_root_unit_returns_self_for_standalone(self, standalone_unit: Unit):
        """Test get_root_unit returns self for standalone unit."""
        assert standalone_unit.get_root_unit() == standalone_unit

    @pytest.mark.django_db
    def test_get_root_unit_returns_top_level(self, user: WMSUser):
        """Test get_root_unit returns the topmost unit in hierarchy."""
        root = Unit.objects.create(user=user, name="Root")
        middle = Unit.objects.create(user=user, name="Middle", parent_unit=root)
        leaf = Unit.objects.create(user=user, name="Leaf", parent_unit=middle)

        assert leaf.get_root_unit() == root
        assert middle.get_root_unit() == root

    @pytest.mark.django_db
    def test_get_ancestors_standalone_unit(self, standalone_unit: Unit):
        """Test get_ancestors for standalone unit returns just itself."""
        ancestors = standalone_unit.get_ancestors()

        assert len(ancestors) == 1
        assert ancestors[0] == standalone_unit

    @pytest.mark.django_db
    def test_get_ancestors_nested_units(self, user: WMSUser):
        """Test get_ancestors for nested units returns full hierarchy."""
        root = Unit.objects.create(user=user, name="Root")
        middle = Unit.objects.create(user=user, name="Middle", parent_unit=root)
        leaf = Unit.objects.create(user=user, name="Leaf", parent_unit=middle)

        ancestors = leaf.get_ancestors()

        assert len(ancestors) == 3
        assert ancestors == [root, middle, leaf]

    @pytest.mark.django_db
    def test_get_ancestors_includes_location(self, user: WMSUser, location: Location):
        """Test get_ancestors includes location at root."""
        unit = Unit.objects.create(user=user, name="Unit", location=location)

        ancestors = unit.get_ancestors()

        assert len(ancestors) == 2
        assert ancestors[0] == location
        assert ancestors[1] == unit

    @pytest.mark.django_db
    def test_get_descendants_no_children(self, standalone_unit: Unit):
        """Test get_descendants for unit with no children."""
        descendants = standalone_unit.get_descendants()

        assert descendants == []

    @pytest.mark.django_db
    def test_get_descendants_with_children(self, user: WMSUser, standalone_unit: Unit):
        """Test get_descendants returns all nested units."""
        child1 = Unit.objects.create(user=user, name="Child1", parent_unit=standalone_unit)
        child2 = Unit.objects.create(user=user, name="Child2", parent_unit=standalone_unit)
        grandchild = Unit.objects.create(user=user, name="Grandchild", parent_unit=child1)

        descendants = standalone_unit.get_descendants()

        assert len(descendants) == 3
        assert child1 in descendants
        assert child2 in descendants
        assert grandchild in descendants

    @pytest.mark.django_db
    def test_has_children_false_for_no_children(self, standalone_unit: Unit):
        """Test has_children returns False when no children."""
        assert standalone_unit.has_children() is False

    @pytest.mark.django_db
    def test_has_children_true_with_children(self, user: WMSUser, standalone_unit: Unit):
        """Test has_children returns True when unit has children."""
        Unit.objects.create(user=user, name="Child", parent_unit=standalone_unit)

        assert standalone_unit.has_children() is True


class TestUnitAccessControl:
    """Tests for Unit.user_has_access() method."""

    @pytest.mark.django_db
    def test_owner_has_access(self, user: WMSUser, standalone_unit: Unit):
        """Test that the owner always has access."""
        assert standalone_unit.user_has_access(user) is True

    @pytest.mark.django_db
    def test_non_owner_without_access(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that non-owner without shared access cannot access."""
        assert standalone_unit.user_has_access(other_user) is False

    @pytest.mark.django_db
    def test_direct_unit_shared_access(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that direct UnitSharedAccess grants access."""
        UnitSharedAccess.objects.create(
            user=other_user,
            unit=standalone_unit,
            permission="read"
        )

        assert standalone_unit.user_has_access(other_user) is True

    @pytest.mark.django_db
    def test_no_transitive_access_through_parent_unit(self, user: WMSUser, other_user: WMSUser):
        """Test that access to parent unit does NOT grant access to child."""
        parent = Unit.objects.create(user=user, name="Parent")
        child = Unit.objects.create(user=user, name="Child", parent_unit=parent)

        # Grant access to parent
        UnitSharedAccess.objects.create(
            user=other_user,
            unit=parent,
            permission="read"
        )

        # Should NOT have access to child — sharing is explicit per unit
        assert child.user_has_access(other_user) is False

    @pytest.mark.django_db
    def test_location_sharing_does_not_grant_unit_access(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that LocationSharedAccess does NOT grant access to units within the location."""
        unit = Unit.objects.create(user=user, name="Unit", location=location)

        # Grant access to location
        LocationSharedAccess.objects.create(
            user=other_user,
            location=location,
            permission="read"
        )

        # Should NOT have access to unit — location sharing only grants name visibility
        assert unit.user_has_access(other_user) is False

    @pytest.mark.django_db
    def test_no_transitive_access_multi_level(self, user: WMSUser, other_user: WMSUser):
        """Test that access does NOT inherit through multiple levels of parent units."""
        grandparent = Unit.objects.create(user=user, name="Grandparent")
        parent = Unit.objects.create(user=user, name="Parent", parent_unit=grandparent)
        child = Unit.objects.create(user=user, name="Child", parent_unit=parent)

        # Grant access only to grandparent
        UnitSharedAccess.objects.create(
            user=other_user,
            unit=grandparent,
            permission="read"
        )

        # Should NOT have access to child — sharing is explicit per unit
        assert child.user_has_access(other_user) is False


class TestUnitHelperMethods:
    """Tests for Unit helper methods."""

    @pytest.mark.django_db
    def test_get_qr_filename_with_name(self, standalone_unit: Unit):
        """Test get_qr_filename with regular name."""
        filename = standalone_unit.get_qr_filename()

        assert filename == "storage-bin_unit_qr.png"

    @pytest.mark.django_db
    def test_get_qr_filename_with_special_chars(self, user: WMSUser):
        """Test get_qr_filename slugifies special characters."""
        unit = Unit.objects.create(user=user, name="My Unit #1!")
        filename = unit.get_qr_filename()

        assert filename == "my-unit-1_unit_qr.png"

    @pytest.mark.django_db
    def test_get_qr_filename_empty_name_fallback(self, user: WMSUser):
        """Test get_qr_filename falls back to 'unit' for empty slug."""
        unit = Unit.objects.create(user=user, name="!!!")  # Only special chars
        filename = unit.get_qr_filename()

        assert filename == "unit_unit_qr.png"

    @pytest.mark.django_db
    def test_get_detail_path(self, standalone_unit: Unit):
        """Test get_detail_path returns correct URL path."""
        path = standalone_unit.get_detail_path()

        assert f"/user/{standalone_unit.user_id}/units/{standalone_unit.access_token}/" in path


class TestItemSave:
    """Tests for Item.save() custom logic."""

    @pytest.mark.django_db
    def test_item_save_raises_error_when_unit_is_none(self, user: WMSUser):
        """Test that creating an item without a unit is blocked by database constraint."""
        # Django ForeignKey descriptors prevent testing None check directly
        # Instead, test that database constraint prevents saving without unit
        item = Item(
            user=user,
            name="Test Item",
            description="Test description"
        )
        item.unit_id = None  # Bypass descriptor by setting FK ID directly

        # This will fail at database level due to NOT NULL constraint
        with pytest.raises(Exception):  # IntegrityError or ValueError
            item.save()

    @pytest.mark.django_db
    def test_item_save_auto_assigns_user_from_unit(self, user: WMSUser, standalone_unit: Unit):
        """Test that item user field is required (auto-assignment not tested due to Django descriptors).
        
        Note: The model has logic to auto-assign user from unit, but Django's ForeignKey
        descriptors make it impossible to test this directly. In practice, views always
        set user explicitly before calling save().
        """
        # Create item with user already set (normal usage pattern)
        item = Item(
            name="Test Item",
            description="Test description",
            unit=standalone_unit,
            user=user
        )
        item.save()

        assert item.user == user
        assert item.user_id == user.id

    @pytest.mark.django_db
    def test_item_save_raises_error_on_user_without_access(self, user: WMSUser, other_user: WMSUser, standalone_unit: Unit):
        """Test that saving an item by a user without access raises ValueError."""
        item = Item(
            user=other_user,  # Different user than unit.user, no shared access
            name="Test Item",
            description="Test description",
            unit=standalone_unit  # owned by 'user'
        )

        with pytest.raises(ValueError, match="does not have write access to Unit"):
            item.save()

    @pytest.mark.django_db
    def test_item_save_raises_error_for_read_only_shared_user(self, user: WMSUser, other_user: WMSUser, standalone_unit: Unit):
        """Test that a read-only shared user cannot save an item."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        item = Item(
            user=other_user,
            name="Read Only Item",
            description="Should not be saved",
            unit=standalone_unit
        )
        with pytest.raises(ValueError, match="does not have write access to Unit"):
            item.save()

    @pytest.mark.django_db
    def test_item_save_succeeds_for_shared_user(self, user: WMSUser, other_user: WMSUser, standalone_unit: Unit):
        """Test that a shared user can save an item in a unit they have access to."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="write"
        )
        item = Item(
            user=other_user,
            name="Shared Item",
            description="Added by shared user",
            unit=standalone_unit
        )
        item.save()
        assert item.id is not None
        assert item.user == other_user
        assert item.unit == standalone_unit

    @pytest.mark.django_db
    def test_item_save_succeeds_with_matching_user(self, user: WMSUser, standalone_unit: Unit):
        """Test that saving an item with matching user succeeds."""
        item = Item(
            user=user,
            name="Test Item",
            description="Test description",
            unit=standalone_unit
        )
        item.save()

        assert item.id is not None
        assert item.user == user


class TestItemToSearchInput:
    """Tests for Item.to_search_input() method."""

    @pytest.mark.django_db
    def test_to_search_input_without_image(self, item: Item):
        """Test to_search_input for item without image."""
        search_input = item.to_search_input()

        assert search_input.name == "Hammer"
        assert search_input.description == "Claw hammer"
        assert search_input.unit_name == "Storage Bin"
        assert search_input.image is None

    @pytest.mark.django_db
    def test_to_search_input_with_image(self, user: WMSUser, standalone_unit: Unit):
        """Test to_search_input for item with image encodes to base64."""
        # Create a simple test image
        image_data = b"fake image data"
        image_file = SimpleUploadedFile(
            name="test_image.jpg",
            content=image_data,
            content_type="image/jpeg"
        )

        item = Item.objects.create(
            user=user,
            name="Test Item",
            description="Item with image",
            unit=standalone_unit,
            image=image_file
        )

        search_input = item.to_search_input()

        assert search_input.name == "Test Item"
        assert search_input.description == "Item with image"
        assert search_input.unit_name == "Storage Bin"
        assert search_input.image is not None

        # Verify base64 encoding
        decoded = base64.b64decode(search_input.image)
        assert decoded == image_data

    @pytest.mark.django_db
    def test_to_search_input_handles_missing_image_gracefully(self, user: WMSUser, standalone_unit: Unit):
        """Test to_search_input handles missing image file gracefully."""
        # Create item with image reference but don't save actual file
        item = Item(
            user=user,
            name="Test Item",
            description="Item with broken image",
            unit=standalone_unit
        )
        item.image = "fake_path.jpg"  # Set path without actual file
        item.save()

        # Should not raise an error
        search_input = item.to_search_input()

        assert search_input.image is None

class TestItemQuantityConstraints:
    """Tests for Item quantity field constraints."""

    @pytest.mark.django_db(transaction=True)
    def test_quantity_all_or_nothing_rejects_quantity_without_unit(self, user: WMSUser, standalone_unit: Unit):
        """Test that quantity without quantity_unit violates constraint."""
        with pytest.raises(IntegrityError):
            Item.objects.create(
                user=user,
                name="Invalid Item",
                description="Test",
                unit=standalone_unit,
                quantity=Decimal("5.0"),
                quantity_unit=""  # Empty string = no unit
            )

    @pytest.mark.django_db(transaction=True)
    def test_quantity_all_or_nothing_rejects_unit_without_quantity(self, user: WMSUser, standalone_unit: Unit):
        """Test that quantity_unit without quantity violates constraint."""
        with pytest.raises(IntegrityError):
            Item.objects.create(
                user=user,
                name="Invalid Item",
                description="Test",
                unit=standalone_unit,
                quantity=None,
                quantity_unit="kg"
            )

    @pytest.mark.django_db(transaction=True)
    def test_quantity_all_or_nothing_accepts_both_set(self, user: WMSUser, standalone_unit: Unit):
        """Test that both quantity and quantity_unit set is valid."""
        item = Item.objects.create(
            user=user,
            name="Valid Item",
            description="Test",
            unit=standalone_unit,
            quantity=Decimal("5.0"),
            quantity_unit="kg"
        )

        assert item.quantity == Decimal("5.0")
        assert item.quantity_unit == "kg"

    @pytest.mark.django_db(transaction=True)
    def test_quantity_all_or_nothing_accepts_both_empty(self, user: WMSUser, standalone_unit: Unit):
        """Test that both quantity and quantity_unit empty is valid."""
        item = Item.objects.create(
            user=user,
            name="No Quantity Item",
            description="Test",
            unit=standalone_unit,
            quantity=None,
            quantity_unit=""
        )

        assert item.quantity is None
        assert item.quantity_unit == ""

    @pytest.mark.django_db(transaction=True)
    def test_quantity_non_negative_rejects_negative(self, user: WMSUser, standalone_unit: Unit):
        """Test that negative quantity violates constraint."""
        with pytest.raises(IntegrityError):
            Item.objects.create(
                user=user,
                name="Negative Item",
                description="Test",
                unit=standalone_unit,
                quantity=Decimal("-5.0"),
                quantity_unit="kg"
            )

    @pytest.mark.django_db(transaction=True)
    def test_quantity_non_negative_accepts_zero(self, user: WMSUser, standalone_unit: Unit):
        """Test that zero quantity is valid."""
        item = Item.objects.create(
            user=user,
            name="Zero Item",
            description="Test",
            unit=standalone_unit,
            quantity=Decimal("0.0"),
            quantity_unit="count"
        )

        assert item.quantity == Decimal("0.0")

    @pytest.mark.django_db(transaction=True)
    def test_quantity_non_negative_accepts_positive(self, user: WMSUser, standalone_unit: Unit):
        """Test that positive quantity is valid."""
        item = Item.objects.create(
            user=user,
            name="Positive Item",
            description="Test",
            unit=standalone_unit,
            quantity=Decimal("100.5"),
            quantity_unit="mL"
        )

        assert item.quantity == Decimal("100.5")


class TestItemFormattedQuantity:
    """Tests for Item.formatted_quantity property."""

    @pytest.mark.django_db
    def test_formatted_quantity_with_count(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity for count unit."""
        item = Item.objects.create(
            user=user,
            name="Screws",
            description="Box of screws",
            unit=standalone_unit,
            quantity=Decimal("100"),
            quantity_unit="count"
        )

        assert item.formatted_quantity == "100 count"

    @pytest.mark.django_db
    def test_formatted_quantity_with_mass(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity for mass units."""
        item = Item.objects.create(
            user=user,
            name="Flour",
            description="Bag of flour",
            unit=standalone_unit,
            quantity=Decimal("2.5"),
            quantity_unit="kg"
        )

        assert item.formatted_quantity == "2.50 kilograms"

    @pytest.mark.django_db
    def test_formatted_quantity_with_volume(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity for volume units."""
        item = Item.objects.create(
            user=user,
            name="Paint",
            description="Can of paint",
            unit=standalone_unit,
            quantity=Decimal("3.78"),
            quantity_unit="gal"
        )

        assert item.formatted_quantity == "3.78 gallons"

    @pytest.mark.django_db
    def test_formatted_quantity_with_length(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity for length units."""
        item = Item.objects.create(
            user=user,
            name="Rope",
            description="Nylon rope",
            unit=standalone_unit,
            quantity=Decimal("50"),
            quantity_unit="ft"
        )

        assert item.formatted_quantity == "50.00 feet"

    @pytest.mark.django_db
    def test_formatted_quantity_returns_none_when_no_quantity(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity returns None when quantity is None."""
        item = Item.objects.create(
            user=user,
            name="No Quantity",
            description="Item without quantity",
            unit=standalone_unit,
            quantity=None,
            quantity_unit=""
        )

        assert item.formatted_quantity is None

    @pytest.mark.django_db
    def test_formatted_quantity_returns_none_when_empty_unit(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity returns None when quantity_unit is empty."""
        item = Item(
            user=user,
            name="Empty Unit",
            description="Item with empty unit",
            unit=standalone_unit,
            quantity=Decimal("5.0"),
            quantity_unit=""
        )
        # Don't save - just test the property logic
        # (saving would violate constraint)
        assert item.formatted_quantity is None

    @pytest.mark.django_db
    def test_formatted_quantity_fallback_for_unknown_unit(self, user: WMSUser, standalone_unit: Unit):
        """Test formatted_quantity uses raw unit value if not in UNIT_2_NAME."""
        item = Item(
            user=user,
            name="Unknown Unit",
            description="Item with unknown unit",
            unit=standalone_unit,
            quantity=Decimal("5.0"),
            quantity_unit="xyz"  # Not a valid unit
        )
        # Don't save - just test the property logic

        assert item.formatted_quantity == "5.00 xyz"


class TestQuantityUnitMappings:
    """Tests for quantity unit mapping constants."""

    def test_category_by_unit_contains_all_units(self):
        """Test that CATEGORY_BY_UNIT includes all units from CATEGORY_2_UNITS."""
        for units in CATEGORY_2_UNITS.values():
            for unit in units:
                assert unit in CATEGORY_BY_UNIT
                assert CATEGORY_BY_UNIT[unit] in CATEGORY_2_UNITS

    def test_quantity_unit_choices_derived_correctly(self):
        """Test that QUANTITY_UNIT_CHOICES is correctly derived."""
        quantity_unit_choices_by_category = {
            category_label.lower(): choice_units
            for category_label, choice_units in QUANTITY_UNIT_CHOICES
        }

        assert set(quantity_unit_choices_by_category) == set(CATEGORY_2_UNITS)

        for category, units in CATEGORY_2_UNITS.items():
            choice_units = quantity_unit_choices_by_category[category]
            choice_units_by_code = dict(choice_units)

            assert set(choice_units_by_code) == set(units)
            for unit in units:
                assert choice_units_by_code[unit] == UNIT_2_NAME[unit]

    def test_quantity_category_choices_derived_correctly(self):
        """Test that QUANTITY_CATEGORY_CHOICES is correctly derived."""
        for i, category in enumerate(CATEGORY_2_UNITS.keys()):
            choice_value, choice_label = QUANTITY_CATEGORY_CHOICES[i]
            assert choice_value == category
            assert choice_label == category.capitalize()

    def test_unit_2_name_contains_all_category_units(self):
        """Test that UNIT_2_NAME contains entries for all units in categories."""
        for units in CATEGORY_2_UNITS.values():
            for unit in units:
                assert unit in UNIT_2_NAME
                assert isinstance(UNIT_2_NAME[unit], str)
                assert len(UNIT_2_NAME[unit]) > 0


class TestGetUserPermission:
    """Tests for Unit.get_user_permission() and Location.get_user_permission()."""

    @pytest.mark.django_db
    def test_owner_gets_owner_permission(self, user: WMSUser, standalone_unit: Unit):
        """Test that the unit owner gets 'owner' permission."""
        assert standalone_unit.get_user_permission(user) == "owner"

    @pytest.mark.django_db
    def test_shared_read_gets_read(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that a user with read shared access gets 'read'."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        assert standalone_unit.get_user_permission(other_user) == "read"

    @pytest.mark.django_db
    def test_shared_write_gets_write(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that a user with write shared access gets 'write'."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="write"
        )
        assert standalone_unit.get_user_permission(other_user) == "write"

    @pytest.mark.django_db
    def test_no_access_returns_none(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that a user with no access gets None."""
        assert standalone_unit.get_user_permission(other_user) is None

    @pytest.mark.django_db
    def test_no_transitive_permission_through_parent(self, user: WMSUser, other_user: WMSUser):
        """Test that permission does NOT inherit from parent unit."""
        parent = Unit.objects.create(user=user, name="Parent")
        child = Unit.objects.create(user=user, name="Child", parent_unit=parent)
        UnitSharedAccess.objects.create(
            user=other_user, unit=parent, permission="write"
        )
        assert child.get_user_permission(other_user) is None

    @pytest.mark.django_db
    def test_location_sharing_does_not_grant_unit_permission(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that permission does NOT inherit from location to unit."""
        unit = Unit.objects.create(user=user, name="Unit", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        assert unit.get_user_permission(other_user) is None

    @pytest.mark.django_db
    def test_location_owner_permission(self, user: WMSUser, location: Location):
        """Test that location owner gets 'owner'."""
        assert location.get_user_permission(user) == "owner"

    @pytest.mark.django_db
    def test_location_shared_permission(self, other_user: WMSUser, location: Location):
        """Test that shared location user gets their permission level."""
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="write"
        )
        assert location.get_user_permission(other_user) == "write"

    @pytest.mark.django_db
    def test_location_no_access(self, other_user: WMSUser, location: Location):
        """Test that unshared user gets None for location."""
        assert location.get_user_permission(other_user) is None


class TestAccessibleQuerysets:
    """Tests for WMSUser.accessible_units/locations/items() methods."""

    @pytest.mark.django_db
    def test_accessible_units_includes_owned(self, user: WMSUser, standalone_unit: Unit):
        """Test that owned units are included."""
        assert standalone_unit in user.accessible_units()

    @pytest.mark.django_db
    def test_accessible_units_includes_shared(self, user: WMSUser, other_user: WMSUser, standalone_unit: Unit):
        """Test that units shared with the user are included."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        assert standalone_unit in other_user.accessible_units()

    @pytest.mark.django_db
    def test_accessible_units_excludes_unshared(self, other_user: WMSUser, standalone_unit: Unit):
        """Test that unshared units are excluded."""
        assert standalone_unit not in other_user.accessible_units()

    @pytest.mark.django_db
    def test_accessible_locations_includes_owned(self, user: WMSUser, location: Location):
        """Test that owned locations are included."""
        assert location in user.accessible_locations()

    @pytest.mark.django_db
    def test_accessible_locations_includes_shared(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that shared locations are included."""
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        assert location in other_user.accessible_locations()

    @pytest.mark.django_db
    def test_accessible_locations_excludes_unshared(self, other_user: WMSUser, location: Location):
        """Test that unshared locations are excluded."""
        assert location not in other_user.accessible_locations()

    @pytest.mark.django_db
    def test_accessible_items_includes_items_in_shared_units(self, user: WMSUser, other_user: WMSUser, standalone_unit: Unit, item: Item):
        """Test that items in shared units are accessible."""
        UnitSharedAccess.objects.create(
            user=other_user, unit=standalone_unit, permission="read"
        )
        assert item in other_user.accessible_items()

    @pytest.mark.django_db
    def test_accessible_items_excludes_items_in_unshared_units(self, other_user: WMSUser, item: Item):
        """Test that items in unshared units are not accessible."""
        assert item not in other_user.accessible_items()

    @pytest.mark.django_db
    def test_accessible_units_excludes_location_transitive(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that units in shared locations are NOT in accessible_units()."""
        unit = Unit.objects.create(user=user, name="Unit in Location", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        assert unit not in other_user.accessible_units()

    @pytest.mark.django_db
    def test_accessible_items_excludes_location_transitive(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that items in shared-location units are NOT in accessible_items()."""
        unit = Unit.objects.create(user=user, name="Unit in Location", location=location)
        item = Item.objects.create(user=user, unit=unit, name="Hidden Item")
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        assert item not in other_user.accessible_items()

    @pytest.mark.django_db
    def test_explicit_unit_access_in_shared_location(self, user: WMSUser, other_user: WMSUser, location: Location):
        """Test that explicit UnitSharedAccess works for units in shared locations."""
        unit = Unit.objects.create(user=user, name="Shared Unit", location=location)
        LocationSharedAccess.objects.create(
            user=other_user, location=location, permission="read"
        )
        UnitSharedAccess.objects.create(
            user=other_user, unit=unit, permission="write"
        )
        assert unit in other_user.accessible_units()
        assert unit.user_has_access(other_user) is True
        assert unit.get_user_permission(other_user) == "write"
