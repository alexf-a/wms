from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from lib.llm.item_generation import extract_item_features_from_image, get_img_str
from lib.llm.llm_search import find_item_location

from .forms import (
    ItemForm,
    ItemSearchForm,
    WMSUserCreationForm,
)
from .models import Bin, Item

logger = logging.getLogger(__name__)

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

def home_view(request: HttpRequest) -> HttpResponse:
    """Render the home page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered home page with content based on authentication status.
    """
    # Pass authentication status to the template
    return render(request, "core/home.html", {"is_authenticated": request.user.is_authenticated})

@login_required
def expand_inventory_view(request: HttpRequest) -> HttpResponse:
    """Render the expand inventory page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered expand inventory page.
    """
    return render(request, "core/expand_inventory.html")

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
            item.save()
            messages.success(request, f"Item '{item.name}' has been added successfully!")
            return redirect("home_view")
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
    return render(request, "core/list_bins.html", {"bins": bins})

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
    selected_bin_id = None

    if request.method == "POST":
        selected_bin_id = request.POST.get("bin_filter")
        form = ItemSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            result = str(find_item_location(query, request.user.id))
    else:
        form = ItemSearchForm()

    return render(request, "core/item_search.html", {
        "form": form,
        "result": result,
        "bins": Bin.objects.filter(user=request.user).order_by("name"),
        "selected_bin_id": selected_bin_id,
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

    if "image" not in request.FILES:
        return JsonResponse({"error": "No image provided"}, status=400)

    try:
        image_file = request.FILES["image"]

        # Extract features using shared function
        result = extract_item_features_from_image(image_file.file)

        return JsonResponse({
            "name": result.name,
            "description": result.description
        })

    except Exception as e:
        logger.exception("Error extracting item features")
        return JsonResponse({"error": "Failed to process image"}, status=500)


def healthcheck_view(_: HttpRequest) -> JsonResponse:  # pragma: no cover - trivial
    """Lightweight healthcheck endpoint.

    Returns 200 with minimal JSON without hitting database.
    """
    return JsonResponse({"status": "ok"})
