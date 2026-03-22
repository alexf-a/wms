"""Access control utilities for views.

Provides helper functions that check whether a user has access to a
resource and return the effective permission level.  When access is
denied the helpers raise Http404 so that the existence of the resource
is not leaked.
"""

from __future__ import annotations

from django.http import Http404

from .models import Item, Location, Unit, WMSUser


def require_unit_access(
    unit: Unit,
    user: WMSUser,
    *,
    require_write: bool = False,
    owner_only: bool = False,
) -> str:
    """Check user access to a Unit, raising Http404 on failure.

    Args:
        unit: The unit to check.
        user: The requesting user.
        require_write: If True, reject read-only shared users.
        owner_only: If True, reject all non-owners.

    Returns:
        The permission level: ``"owner"``, ``"write"``, or ``"read"``.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = unit.get_user_permission(user)
    if perm is None:
        raise Http404("Unit not found")
    if owner_only and perm != "owner":
        raise Http404("Unit not found")
    if require_write and perm == "read":
        raise Http404("Unit not found")
    return perm


def require_location_access(
    location: Location,
    user: WMSUser,
    *,
    require_write: bool = False,
    owner_only: bool = False,
) -> str:
    """Check user access to a Location, raising Http404 on failure.

    Args:
        location: The location to check.
        user: The requesting user.
        require_write: If True, reject read-only shared users.
        owner_only: If True, reject all non-owners.

    Returns:
        The permission level: ``"owner"``, ``"write"``, or ``"read"``.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = location.get_user_permission(user)
    if perm is None:
        raise Http404("Location not found")
    if owner_only and perm != "owner":
        raise Http404("Location not found")
    if require_write and perm == "read":
        raise Http404("Location not found")
    return perm


def require_item_access(
    item: Item,
    user: WMSUser,
    *,
    require_write: bool = False,
) -> str:
    """Check user access to an Item via its Unit, raising Http404 on failure.

    Args:
        item: The item to check.
        user: The requesting user.
        require_write: If True, reject read-only shared users.

    Returns:
        The permission level: ``"owner"``, ``"write"``, or ``"read"``.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = item.unit.get_user_permission(user)
    if perm is None:
        raise Http404("Item not found")
    if require_write and perm == "read":
        raise Http404("Item not found")
    return perm
