from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, F
from django.db.models.functions import Greatest
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from django.core.files.uploadedfile import UploadedFile

import sys
import traceback

from lib.llm.item_generation import extract_item_features_from_image
from lib.llm.llm_search import find_item_location

from .forms import (
    AccountForm,
    ItemForm,
    ItemSearchForm,
    PasswordChangeForm,
    UnitForm,
    WMSUserAuthForm,
    WMSUserCreationForm,
)
from .access import require_item_access, require_location_access, require_unit_access
from .models import UNIT_2_NAME, Item, Location, LocationSharedAccess, Permission, Unit, UnitSharedAccess, WMSUser
from .models import ITEM_QUANTITY_COUNT_STEP, ITEM_QUANTITY_NON_COUNT_STEP, ITEM_QUANTITY_ROUNDING_QUANTUM

logger = logging.getLogger(__name__)

MAX_IMAGE_UPLOAD_SIZE = settings.ITEM_IMAGE_MAX_UPLOAD_SIZE
MAX_IMAGE_DIMENSION = settings.ITEM_IMAGE_MAX_DIMENSION
ALLOWED_IMAGE_FORMATS = {
    fmt.upper() for fmt in settings.ITEM_IMAGE_ALLOWED_FORMATS
}
_max_upload_mb = MAX_IMAGE_UPLOAD_SIZE / (1024 * 1024)
MAX_IMAGE_UPLOAD_SIZE_LABEL = (
    f"{int(_max_upload_mb)}MB"
    if _max_upload_mb.is_integer()
    else f"{_max_upload_mb:.1f}MB"
)
ALLOWED_FORMATS_DISPLAY = ", ".join(sorted(ALLOWED_IMAGE_FORMATS))
QUANTITY_UPDATE_ACTIONS = {"increment", "decrement", "set"}


class ImageValidationError(ValueError):
    """Raised when an uploaded image fails validation."""

    TOO_LARGE = "too_large"
    BAD_FORMAT = "bad_format"
    OVERSIZED_DIMENSIONS = "oversized_dimensions"
    CORRUPTED = "corrupted"

    _MESSAGES: ClassVar[dict[str, str]] = {
        TOO_LARGE: f"Image is too large. Maximum size is {MAX_IMAGE_UPLOAD_SIZE_LABEL}.",
        BAD_FORMAT: (
            "Unsupported image format. Please upload a standard photo "
            f"({ALLOWED_FORMATS_DISPLAY}). If using iPhone, try disabling "
            "HEIC format in Settings > Camera > Formats > Most Compatible."
        ),
        OVERSIZED_DIMENSIONS: (
            f"Image dimensions are too large. Maximum allowed is {MAX_IMAGE_DIMENSION}px on the longest side."
        ),
        CORRUPTED: "Unable to read this image file. Please try a different photo.",
    }

    def __init__(self, reason: str) -> None:
        """Initialize the exception with a predefined reason key."""
        super().__init__(self._MESSAGES[reason])


def _validate_image_upload(image_file: UploadedFile) -> None:
    """Ensure the uploaded image meets size, format, and dimension constraints."""
    logger.debug("Validating image: size=%s, max=%s", image_file.size, MAX_IMAGE_UPLOAD_SIZE)
    if image_file.size > MAX_IMAGE_UPLOAD_SIZE:
        raise ImageValidationError(ImageValidationError.TOO_LARGE)

    try:
        image_file.file.seek(0)
        with Image.open(image_file.file) as img:
            image_format = (img.format or "").upper()
            logger.debug("Image format: %s, allowed: %s", image_format, ALLOWED_IMAGE_FORMATS)
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageValidationError(ImageValidationError.BAD_FORMAT)

            width, height = img.size
            logger.debug("Image dimensions: %sx%s, max=%s", width, height, MAX_IMAGE_DIMENSION)
            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                raise ImageValidationError(ImageValidationError.OVERSIZED_DIMENSIONS)
        logger.debug("Image validation passed")
    except UnidentifiedImageError as exc:
        logger.debug("Image validation failed: corrupted")
        raise ImageValidationError(ImageValidationError.CORRUPTED) from exc
    finally:
        image_file.file.seek(0)

def register_view(request: HttpRequest) -> HttpResponse:
    """Handle user registration.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered registration page or a redirect to the home page.
    """
    # Check if registration is enabled
    if not settings.REGISTRATION_ENABLED:
        messages.error(request, "Registration is currently disabled. Please contact support for access.")
        return redirect("login")

    if request.method == "POST":
        form = WMSUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("onboarding")
        logger.error("Registration form errors: %s", form.errors)
    else:
        form = WMSUserCreationForm()
    return render(request, "core/auth/register.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    """Handle user login with email authentication.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered login page or a redirect to the home page.
    """
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect("home_view")

    if request.method == "POST":
        form = WMSUserAuthForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Redirect to 'next' parameter or home
            next_page = request.GET.get("next", "home_view")
            return redirect(next_page)
    else:
        form = WMSUserAuthForm(request)

    return render(request, "core/auth/login.html", {"form": form})


@login_required
def account_view(request: HttpRequest) -> HttpResponse:
    """Handle user account settings.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered account page with user form.
    """
    if request.method == "POST":
        form = AccountForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Account updated successfully.")
            return redirect("account")
    else:
        form = AccountForm(instance=request.user)
    return render(request, "core/account.html", {"form": form, "active_nav": "account"})


@login_required
def change_password_view(request: HttpRequest) -> HttpResponse:
    """Handle password change for users.
    
    Beta users with must_change_password=True will be forced to this view.
    All users can voluntarily change their password.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered password change page or redirect to home on success.
    """
    # Check if this is a forced password change
    is_forced = getattr(request.user, "must_change_password", False)

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Clear the must_change_password flag
            user.must_change_password = False
            user.save()

            # Re-login user with new password (update session hash)
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)

            messages.success(request, "Your password has been changed successfully.")
            return redirect("home_view")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "core/auth/change_password.html", {
        "form": form,
        "is_forced": is_forced,
    })


def home_view(request: HttpRequest) -> HttpResponse:
    """Render the home page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered home page with content based on authentication status.
    """
    if request.user.is_authenticated and not request.user.has_completed_onboarding:
        return redirect("onboarding")

    context = {
        "is_authenticated": request.user.is_authenticated,
        "active_nav": "home",
    }

    if request.user.is_authenticated:
        context["location_count"] = Location.objects.filter(user=request.user).count()
        context["unit_count"] = Unit.objects.filter(user=request.user).count()
        context["item_count"] = Item.objects.filter(user=request.user).count()

    return render(request, "core/home.html", context)


@login_required
def onboarding_view(request: HttpRequest) -> HttpResponse:
    """Render the onboarding wizard.

    Redirects to home if the user has already completed onboarding.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered onboarding page or a redirect to home.
    """
    if request.user.has_completed_onboarding:
        return redirect("home_view")
    return render(request, "core/onboarding.html")


@login_required
def complete_onboarding_api(request: HttpRequest) -> JsonResponse:
    """Mark the current user as having completed onboarding.

    Args:
        request: The HTTP request object.

    Returns:
        JSON response indicating success or method not allowed.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    request.user.has_completed_onboarding = True
    request.user.save(update_fields=["has_completed_onboarding"])
    return JsonResponse({"status": "ok"})


@login_required
def api_create_location(request: HttpRequest) -> JsonResponse:
    """Create a new location via JSON API.

    Args:
        request: The HTTP request with JSON body containing 'name' and optional 'address'.

    Returns:
        JsonResponse with created location's id and name (201), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    address = (data.get("address") or "").strip() or None

    try:
        location = Location.objects.create(
            user=request.user, name=name, address=address
        )
    except IntegrityError:
        return JsonResponse(
            {"error": f'A location named "{name}" already exists.'}, status=409
        )

    return JsonResponse({"id": location.id, "name": location.name}, status=201)


@login_required
def api_create_unit(request: HttpRequest) -> JsonResponse:
    """Create a new unit via JSON API.

    Args:
        request: The HTTP request with JSON body containing 'name' and optional
            'location_id' or 'parent_unit_id' (mutually exclusive).

    Returns:
        JsonResponse with created unit's id, name, and access_token (201), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    location_id = data.get("location_id")
    parent_unit_id = data.get("parent_unit_id")
    location = None
    parent_unit = None
    if location_id and parent_unit_id:
        return JsonResponse(
            {"error": "A unit cannot have both a location and a parent unit."},
            status=400,
        )
    if location_id:
        location = get_object_or_404(Location, id=location_id)
        require_location_access(location, request.user, require_write=True)
    if parent_unit_id:
        parent_unit = get_object_or_404(Unit, id=parent_unit_id)
        require_unit_access(parent_unit, request.user, require_write=True)

    try:
        unit = Unit.objects.create(
            user=request.user, name=name, location=location, parent_unit=parent_unit,
        )
    except IntegrityError:
        return JsonResponse(
            {"error": f'A unit named "{name}" already exists.'}, status=409
        )

    return JsonResponse(
        {"id": unit.id, "name": unit.name, "access_token": unit.access_token},
        status=201,
    )


@login_required
def api_browse_locations(request: HttpRequest) -> JsonResponse:
    """Return locations with unit counts and orphan units with item counts.

    Args:
        request: The HTTP request object.

    Returns:
        JsonResponse with 'locations' and 'orphan_units' lists.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    locations = (
        request.user.accessible_locations()
        .annotate(unit_count=Count("unit_set"))
        .order_by("name")
        .values("id", "name", "address", "unit_count", "user_id")
    )

    orphan_units = (
        request.user.accessible_units()
        .filter(location__isnull=True, parent_unit__isnull=True)
        .annotate(item_count=Count("items"))
        .order_by("name")
        .values("id", "name", "user_id", "access_token", "item_count")
    )

    return JsonResponse({
        "locations": list(locations),
        "orphan_units": list(orphan_units),
    })


@login_required
def api_browse_location_units(request: HttpRequest, location_id: int) -> JsonResponse:
    """Return units within a location with item and child unit counts.

    For location owners, all units are returned with full data.
    For shared users, units without explicit UnitSharedAccess are
    returned with name only (no contents access).

    Args:
        request: The HTTP request object.
        location_id: The ID of the location to browse.

    Returns:
        JsonResponse with 'location' info, 'permission', and 'units' list.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    perm = require_location_access(location, request.user)

    all_units = (
        Unit.objects.filter(location=location)
        .annotate(
            item_count=Count("items"),
            child_count=Count("child_units"),
        )
        .order_by("name")
    )

    if perm == Permission.OWNER:
        units = [
            {
                "id": u.id,
                "name": u.name,
                "user_id": u.user_id,
                "access_token": u.access_token,
                "item_count": u.item_count,
                "child_count": u.child_count,
                "accessible": True,
            }
            for u in all_units
        ]
    else:
        accessible_ids = set(
            UnitSharedAccess.objects.filter(
                user=request.user, unit__location=location
            ).values_list("unit_id", flat=True)
        ) | set(
            all_units.filter(user=request.user).values_list("id", flat=True)
        )
        units = []
        for u in all_units:
            if u.id in accessible_ids:
                units.append({
                    "id": u.id,
                    "name": u.name,
                    "user_id": u.user_id,
                    "access_token": u.access_token,
                    "item_count": u.item_count,
                    "child_count": u.child_count,
                    "accessible": True,
                })
            else:
                units.append({
                    "id": u.id,
                    "name": u.name,
                    "user_id": u.user_id,
                    "accessible": False,
                })

    return JsonResponse({
        "location": {"id": location.id, "name": location.name},
        "permission": perm,
        "units": units,
    })


@login_required
def api_browse_unit_items(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """Return items and child units within a unit.

    For unit owners, all child units are returned with full data.
    For shared users, child units without explicit UnitSharedAccess
    are returned with name only.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JsonResponse with 'unit' info, 'parent_label', 'child_units', and 'items'.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(
        Unit, user_id=user_id, access_token=access_token
    )
    perm = require_unit_access(unit, request.user)

    all_child_units = (
        Unit.objects.filter(parent_unit=unit)
        .annotate(item_count=Count("items"))
        .order_by("name")
    )

    if perm == Permission.OWNER:
        child_units = [
            {
                "id": cu.id,
                "name": cu.name,
                "user_id": cu.user_id,
                "access_token": cu.access_token,
                "item_count": cu.item_count,
                "accessible": True,
            }
            for cu in all_child_units
        ]
    else:
        accessible_child_ids = set(
            UnitSharedAccess.objects.filter(
                user=request.user, unit__parent_unit=unit
            ).values_list("unit_id", flat=True)
        ) | set(
            all_child_units.filter(user=request.user).values_list("id", flat=True)
        )
        child_units = []
        for cu in all_child_units:
            if cu.id in accessible_child_ids:
                child_units.append({
                    "id": cu.id,
                    "name": cu.name,
                    "user_id": cu.user_id,
                    "access_token": cu.access_token,
                    "item_count": cu.item_count,
                    "accessible": True,
                })
            else:
                child_units.append({
                    "id": cu.id,
                    "name": cu.name,
                    "user_id": cu.user_id,
                    "accessible": False,
                })

    items = unit.items.order_by("name").values(
        "id", "name", "quantity", "quantity_unit"
    )

    parent_label = ""
    if unit.location:
        parent_label = unit.location.name
    elif unit.parent_unit:
        parent_label = unit.parent_unit.name

    return JsonResponse({
        "unit": {"id": unit.id, "name": unit.name},
        "parent_label": parent_label,
        "child_units": child_units,
        "items": list(items),
    })


@login_required
def api_update_location(request: HttpRequest, location_id: int) -> JsonResponse:
    """Update an existing location via JSON API.

    Args:
        request: The HTTP request with JSON body containing 'name' and optional 'address'.
        location_id: The ID of the location to update.

    Returns:
        JsonResponse with updated location data (200), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    location.name = name
    location.address = (data.get("address") or "").strip() or None

    try:
        location.save()
    except IntegrityError:
        return JsonResponse(
            {"error": f'A location named "{name}" already exists.'}, status=409
        )

    return JsonResponse({"id": location.id, "name": location.name, "address": location.address})


@login_required
def api_delete_location(request: HttpRequest, location_id: int) -> JsonResponse:
    """Delete a location via JSON API. Orphans child units.

    Args:
        request: The HTTP request object.
        location_id: The ID of the location to delete.

    Returns:
        JsonResponse with success status (200), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    # Orphan child units before deleting
    location.unit_set.update(location=None)
    location.delete()

    return JsonResponse({"success": True})


@login_required
def api_unit_detail_json(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """Return full unit data for edit dialog population.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JsonResponse with all editable unit fields.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    return JsonResponse({
        "id": unit.id,
        "name": unit.name,
        "description": unit.description or "",
        "location_id": unit.location_id,
        "parent_unit_id": unit.parent_unit_id,
        "length": unit.length,
        "width": unit.width,
        "height": unit.height,
        "dimensions_unit": unit.dimensions_unit or "",
        "user_id": unit.user_id,
        "access_token": unit.access_token,
    })


@login_required
def api_update_unit(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """Update an existing unit via JSON API.

    Args:
        request: The HTTP request with JSON body containing unit fields.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JsonResponse with updated unit data (200), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    # Validate dimensions: all-or-nothing
    length = data.get("length")
    width = data.get("width")
    height = data.get("height")
    dimensions_unit = (data.get("dimensions_unit") or "").strip() or None
    dim_values = [length, width, height, dimensions_unit]
    dim_present = [v is not None and v != "" for v in dim_values]

    if any(dim_present) and not all(dim_present):
        return JsonResponse(
            {"error": "All dimension fields must be provided together, or all left empty."},
            status=400,
        )

    # Validate container: location or parent_unit, not both
    location_id = data.get("location_id")
    parent_unit_id = data.get("parent_unit_id")
    if location_id and parent_unit_id:
        return JsonResponse(
            {"error": "A unit cannot have both a location and a parent unit."},
            status=400,
        )

    unit.name = name
    unit.description = (data.get("description") or "").strip() or None

    # Set container
    if location_id:
        location = get_object_or_404(Location, id=location_id)
        require_location_access(location, request.user, require_write=True)
        unit.location = location
        unit.parent_unit = None
    elif parent_unit_id:
        parent = get_object_or_404(Unit, id=parent_unit_id)
        require_unit_access(parent, request.user, require_write=True)
        unit.parent_unit = parent
        unit.location = None
    else:
        unit.location = None
        unit.parent_unit = None

    # Set dimensions
    if all(dim_present):
        unit.length = float(length)
        unit.width = float(width)
        unit.height = float(height)
        unit.dimensions_unit = dimensions_unit
    else:
        unit.length = None
        unit.width = None
        unit.height = None
        unit.dimensions_unit = None

    try:
        unit.save()
    except IntegrityError:
        return JsonResponse(
            {"error": f'A unit named "{name}" already exists.'}, status=409
        )

    return JsonResponse({
        "id": unit.id, "name": unit.name, "access_token": unit.access_token,
    })


@login_required
def api_delete_unit(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """Delete a unit via JSON API. Orphans child units, cascade-deletes items.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JsonResponse with success status and items deleted count (200), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    # Count items before deletion
    items_count = unit.items.count()

    # Orphan child units before deleting
    unit.child_units.update(parent_unit=None)

    # Delete unit (cascade deletes items)
    unit.delete()

    return JsonResponse({"success": True, "items_deleted": items_count})


@login_required
def api_container_options(request: HttpRequest) -> JsonResponse:
    """Return locations and units available as container options.

    Args:
        request: The HTTP request object. Accepts optional 'exclude_unit' query param.

    Returns:
        JsonResponse with 'locations' and 'units' lists.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    locations = list(
        request.user.accessible_locations()
        .order_by("name")
        .values("id", "name")
    )

    units_qs = request.user.accessible_units().order_by("name")

    exclude_unit = request.GET.get("exclude_unit")
    if exclude_unit:
        try:
            units_qs = units_qs.exclude(id=int(exclude_unit))
        except (ValueError, TypeError):
            pass

    units = list(units_qs.values("id", "name", "user_id", "access_token"))

    return JsonResponse({"locations": locations, "units": units})


def getting_started_view(request: HttpRequest) -> HttpResponse:
    """Render the getting started guide page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered getting started page accessible to all users.
    """
    return render(request, "core/getting_started.html", {"active_nav": None})

@login_required
def expand_inventory_view(request: HttpRequest) -> HttpResponse:
    """Redirect to the add-items page (expand_inventory landing page removed)."""
    return redirect("add_items_to_unit")

@login_required
def create_storage_view(request: HttpRequest) -> HttpResponse:
    """Redirect to the browse page where storage is now created via dialogs."""
    return redirect("list_units")

@login_required
def add_items_to_unit_view(request: HttpRequest) -> HttpResponse:
    """Handle adding items to a unit.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered add items to unit page or a redirect to the home page.
    """
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            require_unit_access(item.unit, request.user, require_write=True)
            try:
                item.save()
                messages.success(request, f"Item '{item.name}' has been added successfully!")
                return redirect("home_view")
            except IntegrityError:
                # Duplicate item name for this user
                form.add_error(
                    "name",
                    f"You already have an item named '{item.name}'. Please choose a different name."
                )
    else:
        initial = {}
        unit_id = request.GET.get("unit")
        if unit_id:
            initial["unit"] = unit_id
        form = ItemForm(user=request.user, initial=initial)

    # Get user's writable units for the template
    units = request.user.writable_units()
    return render(request, "core/add_items_to_unit.html", {
        "form": form,
        "units": units,
        "active_nav": "add",
    })

@login_required
def list_units(request: HttpRequest) -> HttpResponse:
    """List all locations and orphan units for the current user.

    Serves as the browse page's initial data source. Locations include unit
    counts; orphan units include item counts. JS handles drill-down navigation.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered browse page with locations and orphan units.
    """
    locations = (
        Location.objects.filter(user=request.user)
        .annotate(unit_count=Count("unit_set"))
        .order_by("name")
    )
    orphan_units = (
        Unit.objects.filter(
            user=request.user, location__isnull=True, parent_unit__isnull=True
        )
        .annotate(item_count=Count("items"))
        .order_by("name")
    )
    shared_locations = (
        Location.objects.filter(shared_access__user=request.user)
        .annotate(unit_count=Count("unit_set"))
        .order_by("name")
    )
    shared_units = (
        Unit.objects.filter(
            unitsharedaccess__user=request.user,
            location__isnull=True,
            parent_unit__isnull=True,
        )
        .annotate(item_count=Count("items"))
        .order_by("name")
    )
    return render(request, "core/list_units.html", {
        "locations": locations,
        "orphan_units": orphan_units,
        "shared_locations": shared_locations,
        "shared_units": shared_units,
        "active_nav": "see",
    })

@login_required
def unit_detail(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Display the details of a specific unit using its access token.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The opaque access token assigned to the unit.

    Returns:
        The rendered unit detail page.
    """
    _unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    permission = require_unit_access(_unit, request.user)

    accessible_child_ids: set[int] = set()
    if permission != Permission.OWNER:
        accessible_child_ids = set(
            UnitSharedAccess.objects.filter(
                user=request.user, unit__parent_unit=_unit
            ).values_list("unit_id", flat=True)
        ) | set(
            Unit.objects.filter(
                parent_unit=_unit, user=request.user
            ).values_list("id", flat=True)
        )

    return render(request, "core/unit_detail.html", {
        "unit": _unit,
        "permission": permission,
        "accessible_child_ids": accessible_child_ids,
        "unit_2_name_json": json.dumps(UNIT_2_NAME),
        "active_nav": "see",
    })


@login_required
def unit_qr_view(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Return a PNG QR code for the requested unit."""
    _unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(_unit, request.user)

    base_url = request.build_absolute_uri("/")
    qr_file = _unit.get_qr_code(base_url=base_url)
    qr_file.seek(0)

    response = HttpResponse(qr_file.read(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{qr_file.name}"'
    return response

@login_required
def item_detail(request: HttpRequest, item_id: int) -> HttpResponse:
    """Display the details of a specific item.

    Args:
        request: The HTTP request object.
        item_id: The ID of the item.

    Returns:
        The rendered item detail page.
    """
    item = get_object_or_404(Item, id=item_id)
    permission = require_item_access(item, request.user)
    can_write = permission in (Permission.OWNER, Permission.WRITE_ALL) or (
        permission == Permission.WRITE and item.user_id == request.user.id
    )
    return render(request, "core/item_detail.html", {
        "item": item,
        "permission": permission,
        "can_write": can_write,
    })


@login_required
def item_edit_view(request: HttpRequest, item_id: int) -> HttpResponse:
    """Handle editing an existing item.

    Args:
        request: The HTTP request object.
        item_id: The ID of the item to edit.

    Returns:
        The rendered item edit page or a redirect to the item detail page.
    """
    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user, require_write=True)

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, instance=item, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Item '{item.name}' has been updated successfully!")
                return redirect("item_detail", item_id=item.id)
            except IntegrityError:
                form.add_error(
                    "name",
                    f"You already have an item named '{form.cleaned_data['name']}'. Please choose a different name."
                )
    else:
        form = ItemForm(instance=item, user=request.user)

    return render(request, "core/item_edit.html", {"form": form, "item": item})


@login_required
def item_delete_view(request: HttpRequest, item_id: int) -> HttpResponse:
    """Handle deleting an existing item.

    Args:
        request: The HTTP request object.
        item_id: The ID of the item to delete.

    Returns:
        Redirect to the parent unit's detail page.
    """
    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user, require_write=True)

    if request.method != "POST":
        return redirect("item_detail", item_id=item.id)

    # Store parent unit reference before deletion
    parent_unit = item.unit
    item_name = item.name

    # Delete the item
    item.delete()

    messages.success(request, f"Item '{item_name}' has been deleted successfully.")
    return redirect("unit_detail", user_id=parent_unit.user_id, access_token=parent_unit.access_token)


@login_required
def unit_edit_view(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Handle editing an existing unit.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        The rendered unit edit page or a redirect to the unit detail page.
    """
    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    if request.method == "POST":
        form = UnitForm(request.POST, instance=unit, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Unit '{unit.name}' has been updated successfully!")
                return redirect("unit_detail", user_id=unit.user_id, access_token=unit.access_token)
            except IntegrityError:
                form.add_error(
                    "name",
                    f"You already have a unit named '{form.cleaned_data['name']}'. Please choose a different name."
                )
    else:
        form = UnitForm(instance=unit, user=request.user)

    return render(request, "core/unit_edit.html", {"form": form, "unit": unit})


@login_required
def unit_delete_view(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Handle deleting an existing unit.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        Redirect to the units list page.
    """
    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    if request.method != "POST":
        return redirect("unit_detail", user_id=unit.user_id, access_token=unit.access_token)

    unit_name = unit.name

    # Delete the unit (cascade will handle items and child units)
    unit.delete()

    messages.success(request, f"Unit '{unit_name}' has been deleted successfully.")
    return redirect("list_units")


@login_required
def item_search_view(request: HttpRequest) -> HttpResponse:
    """Handle item search using LLM.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered search page with results if query provided.
    """
    result = None
    found_item = None
    selected_unit_id = None

    if request.method == "POST":
        selected_unit_id = request.POST.get("unit_filter")
        form = ItemSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            item_location = find_item_location(query, request.user.id)
            # Only show results when the item actually exists in accessible inventory
            found_item = request.user.accessible_items().filter(
                name=item_location.item_name,
            ).first()
            if found_item:
                result = str(item_location)
    else:
        form = ItemSearchForm()

    return render(request, "core/item_search.html", {
        "form": form,
        "result": result,
        "found_item": found_item,
        "units": request.user.accessible_units().order_by("name"),
        "selected_unit_id": selected_unit_id,
        "active_nav": "find",
    })


@login_required
def extract_item_features_api(request: HttpRequest) -> JsonResponse:
    """Extract item features from an uploaded image via API.

    Process an image and return extracted name and description
    without saving to the database. Used for the new hero-action flow.

    Args:
        request: The HTTP request object with uploaded image file.

    Returns:
        JsonResponse with extracted 'name' and 'description' fields.
    """
    logger.info("[ExtractAPI] Request received - method=%s, user=%s", request.method, request.user)

    if request.method != "POST":
        logger.warning("[ExtractAPI] Invalid method: %s", request.method)
        return JsonResponse({"error": "POST method required"}, status=405)

    # Debug logging for file upload issues
    logger.info("[ExtractAPI] FILES keys: %s, POST keys: %s, Content-Type: %s",
                 list(request.FILES.keys()),
                 list(request.POST.keys()),
                 request.content_type)

    if "image" not in request.FILES:
        logger.warning("[ExtractAPI] No 'image' in FILES. Full FILES: %s", request.FILES)
        return JsonResponse({"error": "No image provided"}, status=400)

    image_file = request.FILES["image"]
    logger.info("[ExtractAPI] Got image file: name=%s, size=%s, content_type=%s",
                image_file.name, image_file.size, getattr(image_file, "content_type", "unknown"))

    try:
        _validate_image_upload(image_file)
        logger.info("[ExtractAPI] Image validation passed, calling LLM...")
        result = extract_item_features_from_image(image_file.file)
        logger.info("[ExtractAPI] LLM extraction successful: name=%s", result.name)
        return JsonResponse({
            "name": result.name,
            "description": result.description
        })
    except ImageValidationError as validation_error:
        logger.warning("[ExtractAPI] Image validation error: %s", validation_error)
        return JsonResponse({"error": str(validation_error)}, status=400)
    except Exception:
        logger.exception("[ExtractAPI] Exception during extraction")
        return JsonResponse({"error": "Failed to process image"}, status=500)


@login_required
def update_item_quantity_api(request: HttpRequest, item_id: int) -> JsonResponse:  # noqa: C901, PLR0911
    """Update an item's quantity via AJAX API.

    Supports three actions:
    - increment: Increase quantity by step (1 for count, 0.1 for others)
    - decrement: Decrease quantity by step (clamped to 0 minimum)
    - set: Set quantity to specific value

    Args:
        request: The HTTP request object with action and optional value in POST data.
        item_id: The ID of the item to update.

    Returns:
        JsonResponse with updated 'quantity' and 'formatted' fields, or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        item = Item.objects.select_related("unit").get(id=item_id)
    except Item.DoesNotExist:
        return JsonResponse({"error": "Item not found"}, status=404)

    # Verify access with write permission
    require_item_access(item, request.user, require_write=True)

    # Item must have quantity/unit set to be updatable
    if item.quantity is None or not item.quantity_unit:
        return JsonResponse({"error": "Item does not have quantity tracking enabled"}, status=400)

    # Parse action
    action = request.POST.get("action")
    if action not in QUANTITY_UPDATE_ACTIONS:
        valid_actions = ", ".join(f"'{a}'" for a in QUANTITY_UPDATE_ACTIONS)
        return JsonResponse({"error": f"Invalid action. Must be {valid_actions}"}, status=400)

    # Determine step size: 1 for count, 0.1 for all others
    step = ITEM_QUANTITY_COUNT_STEP if item.quantity_unit == "count" else ITEM_QUANTITY_NON_COUNT_STEP

    try:
        if action == "set":
            value_str = request.POST.get("value")
            if value_str is None:
                return JsonResponse({"error": "Missing 'value' parameter for 'set' action"}, status=400)
            new_quantity = Decimal(value_str)
            # Clamp to 0 minimum
            new_quantity = max(Decimal(0), new_quantity)
            # Truncate to integer for count units, round non-count units
            new_quantity = Decimal(int(new_quantity)) if item.quantity_unit == "count" else new_quantity.quantize(ITEM_QUANTITY_ROUNDING_QUANTUM)

            # Update with direct assignment
            item.quantity = new_quantity
            item.save(update_fields=["quantity"])
        elif action == "increment":
            # Atomic increment with F() expression
            Item.objects.filter(id=item_id).update(quantity=F("quantity") + step)
            item.refresh_from_db()
        else:  # decrement
            # Atomic decrement with Greatest() to ensure non-negative
            clamp = Decimal(0)
            Item.objects.filter(id=item_id).update(
                quantity=Greatest(F("quantity") - step, clamp)
            )
            item.refresh_from_db()

        return JsonResponse({
            "quantity": float(item.quantity),
            "formatted": item.formatted_quantity or ""
        })

    except (InvalidOperation, ValueError, TypeError) as e:
        return JsonResponse({"error": f"Invalid value: {e}"}, status=400)
    except Exception:
        logger.exception("[UpdateQuantityAPI] Unexpected error")
        return JsonResponse({"error": "Failed to update quantity"}, status=500)


# =============================================================================
# Item CRUD JSON APIs (Phase 8)
# =============================================================================


@login_required
def api_item_detail_json(request: HttpRequest, item_id: int) -> JsonResponse:
    """Return item fields as JSON for the detail bottom sheet.

    Args:
        request: The HTTP request object.
        item_id: The database ID of the item.

    Returns:
        JSON with item name, description, quantity, unit, image URL, and timestamps.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user)

    return JsonResponse({
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "image_url": item.image.url if item.image else None,
        "quantity": float(item.quantity) if item.quantity is not None else None,
        "quantity_unit": item.quantity_unit or None,
        "formatted_quantity": item.formatted_quantity,
        "unit_id": item.unit_id,
        "unit_name": item.unit.name,
        "user_id": item.user_id,
        "created_on": item.created_on.isoformat(),
    })


@login_required
def api_update_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Update an item's name, description, or quantity via JSON POST.

    Args:
        request: The HTTP request object.
        item_id: The database ID of the item.

    Returns:
        JSON confirmation with updated item fields.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user, require_write=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    item.name = name
    item.description = data.get("description", "").strip()

    try:
        item.save()
    except IntegrityError:
        return JsonResponse(
            {"error": f"You already have an item named '{name}'."},
            status=409,
        )

    return JsonResponse({
        "id": item.id,
        "name": item.name,
        "description": item.description,
    })


@login_required
def api_delete_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Delete an item via POST.

    Args:
        request: The HTTP request object.
        item_id: The database ID of the item.

    Returns:
        JSON confirmation with the deleted item's name.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user, require_write=True)
    item_name = item.name
    item.delete()

    return JsonResponse({"status": "deleted", "name": item_name})


@login_required
def api_move_item(request: HttpRequest, item_id: int) -> JsonResponse:
    """Move an item to a different unit via POST.

    Args:
        request: The HTTP request object.
        item_id: The database ID of the item.

    Returns:
        JSON confirmation with the new unit details.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item = get_object_or_404(Item, id=item_id)
    require_item_access(item, request.user, require_write=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    target_unit_id = data.get("unit_id")
    if not target_unit_id:
        return JsonResponse({"error": "unit_id is required"}, status=400)

    target_unit = get_object_or_404(Unit, id=target_unit_id)
    require_unit_access(target_unit, request.user, require_write=True)

    item.unit = target_unit
    item.save(update_fields=["unit"])

    return JsonResponse({
        "id": item.id,
        "unit_id": target_unit.id,
        "unit_name": target_unit.name,
    })


def healthcheck_view(_: HttpRequest) -> JsonResponse:  # pragma: no cover - trivial
    """Lightweight healthcheck endpoint.

    Returns 200 with minimal JSON without hitting database.
    """
    return JsonResponse({"status": "ok"})


def caddy_ca_download_view(request: HttpRequest) -> HttpResponse:
    """Serve Caddy root CA certificate for local HTTPS testing.

    This endpoint allows mobile devices to download the Caddy Local Authority
    root certificate to trust local HTTPS connections during development.
    No authentication required to facilitate easy mobile setup.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse with CA certificate file or 404 JsonResponse if not found.
    """
    ca_cert_path = Path(settings.BASE_DIR) / "deploy" / "caddy-root-ca.crt"

    if not ca_cert_path.exists():
        return JsonResponse(
            {
                "error": "CA certificate not found",
                "message": "Run 'make caddy-export-ca' to extract the certificate first.",
            },
            status=404,
        )

    try:
        with Path.open(ca_cert_path, "rb") as cert_file:
            response = HttpResponse(cert_file.read(), content_type="application/x-pem-file")
            response["Content-Disposition"] = 'attachment; filename="caddy-root-ca.crt"'
            return response
    except Exception as e:
        logger.exception("Error serving Caddy CA certificate")
        return JsonResponse(
            {"error": "Failed to read certificate file", "details": str(e)},
            status=500,
        )


# =============================================================================
# Sharing Management APIs
# =============================================================================

_VALID_PERMISSIONS = Permission.storable()


@login_required
def api_unit_sharing(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """List users with shared access to a unit.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JSON with list of shared access records.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    shares = UnitSharedAccess.objects.filter(unit=unit).select_related("user")
    return JsonResponse({
        "shares": [
            {"id": s.id, "email": s.user.email, "permission": s.permission}
            for s in shares
        ]
    })


@login_required
def api_unit_sharing_add(request: HttpRequest, user_id: int, access_token: str) -> JsonResponse:
    """Invite a user to a unit by email.

    Args:
        request: The HTTP request object with JSON body containing 'email' and 'permission'.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.

    Returns:
        JSON with created share record (201), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = (data.get("email") or "").strip().lower()
    permission = data.get("permission", "read")

    if permission not in _VALID_PERMISSIONS:
        return JsonResponse({"error": "Invalid permission"}, status=400)
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    try:
        target_user = WMSUser.objects.get(email=email)
    except WMSUser.DoesNotExist:
        return JsonResponse({"error": "No user with that email"}, status=404)

    if target_user == request.user:
        return JsonResponse({"error": "Cannot share with yourself"}, status=400)

    access, created = UnitSharedAccess.objects.get_or_create(
        user=target_user, unit=unit, defaults={"permission": permission}
    )
    if not created:
        return JsonResponse({"error": "Already shared with this user"}, status=409)

    return JsonResponse(
        {"id": access.id, "email": email, "permission": permission}, status=201
    )


@login_required
def api_unit_sharing_remove(request: HttpRequest, user_id: int, access_token: str, access_id: int) -> JsonResponse:
    """Revoke a user's shared access to a unit.

    Args:
        request: The HTTP request object.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.
        access_id: The ID of the UnitSharedAccess record.

    Returns:
        JSON confirmation.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    access = get_object_or_404(UnitSharedAccess, id=access_id, unit=unit)
    access.delete()
    return JsonResponse({"status": "removed"})


@login_required
def api_unit_sharing_update(request: HttpRequest, user_id: int, access_token: str, access_id: int) -> JsonResponse:
    """Update a shared user's permission level on a unit.

    Args:
        request: The HTTP request object with JSON body containing 'permission'.
        user_id: The ID of the unit owner.
        access_token: The unit's access token.
        access_id: The ID of the UnitSharedAccess record.

    Returns:
        JSON with updated permission.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    unit = get_object_or_404(Unit, user_id=user_id, access_token=access_token)
    require_unit_access(unit, request.user, owner_only=True)

    access = get_object_or_404(UnitSharedAccess, id=access_id, unit=unit)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    permission = data.get("permission")
    if permission not in _VALID_PERMISSIONS:
        return JsonResponse({"error": "Invalid permission"}, status=400)

    access.permission = permission
    access.save(update_fields=["permission"])
    return JsonResponse({"id": access.id, "permission": permission})


@login_required
def api_location_sharing(request: HttpRequest, location_id: int) -> JsonResponse:
    """List users with shared access to a location.

    Args:
        request: The HTTP request object.
        location_id: The ID of the location.

    Returns:
        JSON with list of shared access records.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    shares = LocationSharedAccess.objects.filter(location=location).select_related("user")
    return JsonResponse({
        "shares": [
            {"id": s.id, "email": s.user.email, "permission": s.permission}
            for s in shares
        ]
    })


@login_required
def api_location_sharing_add(request: HttpRequest, location_id: int) -> JsonResponse:
    """Invite a user to a location by email.

    Args:
        request: The HTTP request object with JSON body containing 'email' and 'permission'.
        location_id: The ID of the location.

    Returns:
        JSON with created share record (201), or error.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    email = (data.get("email") or "").strip().lower()
    permission = data.get("permission", "read")

    if permission not in _VALID_PERMISSIONS:
        return JsonResponse({"error": "Invalid permission"}, status=400)
    if not email:
        return JsonResponse({"error": "Email is required"}, status=400)

    try:
        target_user = WMSUser.objects.get(email=email)
    except WMSUser.DoesNotExist:
        return JsonResponse({"error": "No user with that email"}, status=404)

    if target_user == request.user:
        return JsonResponse({"error": "Cannot share with yourself"}, status=400)

    access, created = LocationSharedAccess.objects.get_or_create(
        user=target_user, location=location, defaults={"permission": permission}
    )
    if not created:
        return JsonResponse({"error": "Already shared with this user"}, status=409)

    return JsonResponse(
        {"id": access.id, "email": email, "permission": permission}, status=201
    )


@login_required
def api_location_sharing_remove(request: HttpRequest, location_id: int, access_id: int) -> JsonResponse:
    """Revoke a user's shared access to a location.

    Args:
        request: The HTTP request object.
        location_id: The ID of the location.
        access_id: The ID of the LocationSharedAccess record.

    Returns:
        JSON confirmation.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    access = get_object_or_404(LocationSharedAccess, id=access_id, location=location)
    access.delete()
    return JsonResponse({"status": "removed"})


@login_required
def api_location_sharing_update(request: HttpRequest, location_id: int, access_id: int) -> JsonResponse:
    """Update a shared user's permission level on a location.

    Args:
        request: The HTTP request object with JSON body containing 'permission'.
        location_id: The ID of the location.
        access_id: The ID of the LocationSharedAccess record.

    Returns:
        JSON with updated permission.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    location = get_object_or_404(Location, id=location_id)
    require_location_access(location, request.user, owner_only=True)

    access = get_object_or_404(LocationSharedAccess, id=access_id, location=location)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    permission = data.get("permission")
    if permission not in _VALID_PERMISSIONS:
        return JsonResponse({"error": "Invalid permission"}, status=400)

    access.permission = permission
    access.save(update_fields=["permission"])
    return JsonResponse({"id": access.id, "permission": permission})


# =============================================================================
# Custom Error Handlers
# =============================================================================


def custom_400_view(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Handle 400 Bad Request errors with optional debug info."""
    context = {
        "debug": settings.DEBUG,
        "exception": str(exception) if exception else None,
        "traceback": traceback.format_exc() if settings.DEBUG and exception is not None else None,
    }
    return render(request, "400.html", context, status=400)


def custom_403_view(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Handle 403 Forbidden errors with optional debug info."""
    context = {
        "debug": settings.DEBUG,
        "exception": str(exception) if exception else None,
        "traceback": traceback.format_exc() if settings.DEBUG and exception is not None else None,
    }
    return render(request, "403.html", context, status=403)


def custom_404_view(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Handle 404 Not Found errors with optional debug info."""
    context = {
        "debug": settings.DEBUG,
        "exception": str(exception) if exception else None,
        "request_path": request.path,
    }
    return render(request, "404.html", context, status=404)


def custom_500_view(request: HttpRequest) -> HttpResponse:
    """Handle 500 Internal Server errors with optional debug info."""
    exc_info = sys.exc_info()
    context = {
        "debug": settings.DEBUG,
        "exception": str(exc_info[1]) if exc_info[1] else None,
        "exception_type": exc_info[0].__name__ if exc_info[0] else None,
        "traceback": traceback.format_exc() if settings.DEBUG else None,
    }
    return render(request, "500.html", context, status=500)
