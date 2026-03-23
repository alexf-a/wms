"""Access control utilities for views.

Provides helper functions that check whether a user has access to a
resource and return the effective permission level.  When access is
denied the helpers raise Http404 so that the existence of the resource
is not leaked.
"""

from __future__ import annotations

from django.http import Http404

from .models import Item, Location, Permission, Unit, WMSUser


def require_unit_access(
    unit: Unit,
    user: WMSUser,
    *,
    require_write: bool = False,
    owner_only: bool = False,
) -> Permission:
    """Check user access to a Unit, raising Http404 on failure.

    Args:
        unit: The unit to check.
        user: The requesting user.
        require_write: If True, reject read-only shared users.
        owner_only: If True, reject all non-owners.

    Returns:
        The effective Permission for this user.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = unit.get_user_permission(user)
    if perm is None:
        raise Http404("Unit not found")
    if owner_only and perm != Permission.OWNER:
        raise Http404("Unit not found")
    if require_write and perm == Permission.READ:
        raise Http404("Unit not found")
    return perm


def require_location_access(
    location: Location,
    user: WMSUser,
    *,
    require_write: bool = False,
    owner_only: bool = False,
) -> Permission:
    """Check user access to a Location, raising Http404 on failure.

    Args:
        location: The location to check.
        user: The requesting user.
        require_write: If True, reject read-only shared users.
        owner_only: If True, reject all non-owners.

    Returns:
        The effective Permission for this user.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = location.get_user_permission(user)
    if perm is None:
        raise Http404("Location not found")
    if owner_only and perm != Permission.OWNER:
        raise Http404("Location not found")
    if require_write and perm == Permission.READ:
        raise Http404("Location not found")
    return perm


def require_item_access(
    item: Item,
    user: WMSUser,
    *,
    require_write: bool = False,
) -> Permission:
    """Check user access to an Item via its Unit, raising Http404 on failure.

    When ``require_write`` is True, ownership enforcement applies:
    - ``OWNER`` and ``WRITE_ALL`` may edit/delete any item.
    - ``WRITE`` may only edit/delete items they own (``item.user == user``).
    - ``READ`` is always denied for write operations.

    Args:
        item: The item to check.
        user: The requesting user.
        require_write: If True, reject users without sufficient write access.

    Returns:
        The effective Permission for this user.

    Raises:
        Http404: If the user lacks sufficient access.
    """
    perm = item.unit.get_user_permission(user)
    if perm is None:
        raise Http404("Item not found")
    if require_write:
        if perm == Permission.READ:
            msg = "Item not found"
            raise Http404(msg)
        if perm == Permission.WRITE and item.user_id != user.id:
            msg = "Item not found"
            raise Http404(msg)
    return perm
