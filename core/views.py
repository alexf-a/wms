from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
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
    WMSUserCreationForm,
)
from .models import Bin, Item

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
    if request.method == "POST":
        form = WMSUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
        logger.error("Registration form errors: %s", form.errors)
    else:
        form = WMSUserCreationForm()
    return render(request, "core/auth/register.html", {"form": form})


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

def home_view(request: HttpRequest) -> HttpResponse:
    """Render the home page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered home page with content based on authentication status.
    """
    # Pass authentication status to the template
    return render(request, "core/home.html", {"is_authenticated": request.user.is_authenticated, "active_nav": "home"})

@login_required
def expand_inventory_view(request: HttpRequest) -> HttpResponse:
    """Render the expand inventory page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered expand inventory page.
    """
    return render(request, "core/expand_inventory.html", {"active_nav": "add"})

@login_required
def create_bin_view(request: HttpRequest) -> HttpResponse:
    """Handle the creation of a new bin.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered create bin page or a redirect to the home page.
    """
    if request.method == "POST":
        name = request.POST["name"]
        description = request.POST["description"]
        location = request.POST.get("location", "")
        length = request.POST.get("length") or None
        width = request.POST.get("width") or None
        height = request.POST.get("height") or None
        new_bin = Bin(
            user=request.user,
            name=name,
            description=description,
            location=location,
            length=length,
            width=width,
            height=height,
        )
        new_bin.save()
        return redirect("home_view")
    return render(request, "core/create_bin.html")

@login_required
def add_items_to_bin_view(request: HttpRequest) -> HttpResponse:
    """Handle adding items to a bin.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered add items to bin page or a redirect to the home page.
    """
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
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
        form = ItemForm(user=request.user)

    # Get user's bins for the template
    bins = Bin.objects.filter(user=request.user)
    return render(request, "core/add_items_to_bin.html", {"form": form, "bins": bins})

@login_required
def list_bins(request: HttpRequest) -> HttpResponse:
    """List all bins for the current user.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered list bins page.
    """
    bins = Bin.objects.filter(user=request.user)
    return render(request, "core/list_bins.html", {"bins": bins, "active_nav": "see"})

@login_required
def bin_detail(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Display the details of a specific bin using its access token.

    Args:
        request: The HTTP request object.
        user_id: The ID of the bin owner.
        access_token: The opaque access token assigned to the bin.

    Returns:
        The rendered bin detail page.
    """
    _bin = get_object_or_404(Bin, user_id=user_id, access_token=access_token)
    return render(request, "core/bin_detail.html", {"bin": _bin})


@login_required
def bin_qr_view(request: HttpRequest, user_id: int, access_token: str) -> HttpResponse:
    """Return a PNG QR code for the requested bin."""
    _bin = get_object_or_404(Bin, user_id=user_id, access_token=access_token)
    has_access = _bin.user_id == request.user.id or _bin.shared_users.filter(id=request.user.id).exists()
    if not has_access:
        message = "Bin not found."
        raise Http404(message)

    base_url = request.build_absolute_uri("/")
    qr_file = _bin.get_qr_code(base_url=base_url)
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
    return render(request, "core/item_detail.html", {"item": item})

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
    selected_bin_id = None

    if request.method == "POST":
        selected_bin_id = request.POST.get("bin_filter")
        form = ItemSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            item_location = find_item_location(query, request.user.id)
            result = str(item_location)
            # Try to fetch the actual Item object for displaying its image
            found_item = Item.objects.filter(
                user=request.user,
                name=item_location.item_name,
            ).first()
    else:
        form = ItemSearchForm()

    return render(request, "core/item_search.html", {
        "form": form,
        "result": result,
        "found_item": found_item,
        "bins": Bin.objects.filter(user=request.user).order_by("name"),
        "selected_bin_id": selected_bin_id,
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
    if request.method != "POST":
        return JsonResponse({"error": "POST method required"}, status=405)

    # Debug logging for file upload issues
    logger.debug("Extract API - FILES keys: %s, POST keys: %s, Content-Type: %s",
                 list(request.FILES.keys()),
                 list(request.POST.keys()),
                 request.content_type)

    if "image" not in request.FILES:
        logger.debug("No 'image' in FILES. Full FILES: %s", request.FILES)
        return JsonResponse({"error": "No image provided"}, status=400)

    image_file = request.FILES["image"]
    logger.debug("Got image file: %s, size: %s", image_file.name, image_file.size)

    try:
        _validate_image_upload(image_file)
        logger.debug("Calling extract_item_features_from_image...")
        result = extract_item_features_from_image(image_file.file)
        logger.debug("Extraction successful: name=%s", result.name)
        return JsonResponse({
            "name": result.name,
            "description": result.description
        })
    except ImageValidationError as validation_error:
        logger.debug("Image validation error: %s", validation_error)
        return JsonResponse({"error": str(validation_error)}, status=400)
    except Exception:
        logger.exception("Error extracting item features")
        return JsonResponse({"error": "Failed to process image"}, status=500)


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
