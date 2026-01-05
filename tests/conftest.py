"""Shared pytest fixtures for testing WMS models and views."""

import pytest

from core.models import WMSUser, Location, Unit, Item


@pytest.fixture
def user(db):
    """Create a test user with email-based authentication."""
    return WMSUser.objects.create_user(
        email="owner@example.com",
        password="testpass123"
    )


@pytest.fixture
def other_user(db):
    """Create a second test user for access control tests."""
    return WMSUser.objects.create_user(
        email="other@example.com",
        password="testpass123"
    )


@pytest.fixture
def location(user):
    """Create a test location for the primary user."""
    return Location.objects.create(
        user=user,
        name="My House",
        description="Test location",
        address="123 Test St"
    )


@pytest.fixture
def unit_in_location(user, location):
    """Create a unit inside a location."""
    return Unit.objects.create(
        user=user,
        name="Garage",
        description="Test unit in location",
        location=location
    )


@pytest.fixture
def standalone_unit(user):
    """Create a standalone unit with no parent."""
    return Unit.objects.create(
        user=user,
        name="Storage Bin",
        description="Standalone test unit"
    )


@pytest.fixture
def unit_with_dimensions(user):
    """Create a unit with complete dimensions."""
    return Unit.objects.create(
        user=user,
        name="Toolbox",
        description="Red toolbox",
        length=24.0,
        width=12.0,
        height=8.0,
        dimensions_unit='in'
    )


@pytest.fixture
def nested_unit(user, standalone_unit):
    """Create a unit nested inside another unit."""
    return Unit.objects.create(
        user=user,
        name="Drawer",
        description="Drawer inside storage bin",
        parent_unit=standalone_unit
    )


@pytest.fixture
def item(user, standalone_unit):
    """Create a test item in a unit."""
    return Item.objects.create(
        user=user,
        name="Hammer",
        description="Claw hammer",
        unit=standalone_unit
    )
