"""Shared pytest fixtures for testing WMS models and views."""

from __future__ import annotations

from typing import Callable, Optional
from unittest.mock import Mock

import pytest

from core.models import Item, Location, Unit, WMSUser


@pytest.fixture
def user(db) -> WMSUser:
    """Create a test user with email-based authentication."""
    return WMSUser.objects.create_user(
        email="owner@example.com",
        password="testpass123"
    )


@pytest.fixture
def other_user(db) -> WMSUser:
    """Create a second test user for access control tests."""
    return WMSUser.objects.create_user(
        email="other@example.com",
        password="testpass123"
    )


@pytest.fixture
def location(user: WMSUser) -> Location:
    """Create a test location for the primary user."""
    return Location.objects.create(
        user=user,
        name="My House",
        description="Test location",
        address="123 Test St"
    )


@pytest.fixture
def unit_in_location(user: WMSUser, location: Location) -> Unit:
    """Create a unit inside a location."""
    return Unit.objects.create(
        user=user,
        name="Garage",
        description="Test unit in location",
        location=location
    )


@pytest.fixture
def standalone_unit(user: WMSUser) -> Unit:
    """Create a standalone unit with no parent."""
    return Unit.objects.create(
        user=user,
        name="Storage Bin",
        description="Standalone test unit"
    )


@pytest.fixture
def unit_with_dimensions(user: WMSUser) -> Unit:
    """Create a unit with complete dimensions."""
    return Unit.objects.create(
        user=user,
        name="Toolbox",
        description="Red toolbox",
        length=24.0,
        width=12.0,
        height=8.0,
        dimensions_unit="in"
    )


@pytest.fixture
def nested_unit(user: WMSUser, standalone_unit: Unit) -> Unit:
    """Create a unit nested inside another unit."""
    return Unit.objects.create(
        user=user,
        name="Drawer",
        description="Drawer inside storage bin",
        parent_unit=standalone_unit
    )


@pytest.fixture
def item(user: WMSUser, standalone_unit: Unit) -> Item:
    """Create a test item in a unit."""
    return Item.objects.create(
        user=user,
        name="Hammer",
        description="Claw hammer",
        unit=standalone_unit
    )


@pytest.fixture
def mock_path() -> Callable[[bool, Optional[bytes]], Mock]:
    """Create a mock Path that supports / operator and context manager.
    
    Returns a factory function that creates a configured mock Path instance.
    The mock supports chaining with / operator and can be configured for exists()
    and open() operations.
    
    Usage:
        @patch("module.Path")
        def test_something(self, mock_path_class, mock_path):
            path_instance = mock_path(exists=False)
            mock_path_class.return_value = path_instance
    """
    def _create_mock_path(exists: bool = True, file_content: bytes | None = None) -> Mock:
        """Create a configured mock Path instance.

        Args:
            exists: Whether the path exists (default: True)
            file_content: Content to return when opened (bytes or None)

        Returns:
            Mock object configured to act like a Path
        """
        mock_instance = Mock()
        # Support / operator by returning self
        mock_instance.__truediv__ = Mock(return_value=mock_instance)
        mock_instance.exists.return_value = exists

        if file_content is not None:
            from io import BytesIO
            mock_file = BytesIO(file_content)
            # Support both Path.open(path) and path.open()
            mock_instance.open = Mock(return_value=mock_file)
            mock_instance.__enter__ = Mock(return_value=mock_file)
            mock_instance.__exit__ = Mock(return_value=False)

        return mock_instance

    return _create_mock_path
