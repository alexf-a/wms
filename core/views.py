import logging
logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from lib.llm.item_generation import get_item_from_img
from lib.llm.llm_search import find_item_location

from .forms import (
    AutoGenerateItemForm,
    ConfirmItemForm,
    ItemForm,
    ItemSearchForm,
    WMSUserCreationForm,
)
from .models import Bin, Item
from .utils import get_qr_code_file

def register_view(request: HttpRequest) -> render:
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
        # DEBUG: log form errors
        logger.error("Registration form errors: %s", form.errors)
    else:
        form = WMSUserCreationForm()
    return render(request, "core/auth/register.html", {"form": form})

def home_view(request: HttpRequest) -> render:
    """Render the home page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered home page with content based on authentication status.
    """
    # Pass authentication status to the template
    return render(request, "core/home.html", {"is_authenticated": request.user.is_authenticated})

def expand_inventory_view(request: HttpRequest) -> render:
    """Render the expand inventory page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered expand inventory page.
    """
    return render(request, "core/expand_inventory.html")

@login_required
def create_bin_view(request: HttpRequest) -> render:
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
        length = request.POST.get("length", None)
        width = request.POST.get("width", None)
        height = request.POST.get("height", None)

        qr_code_file = get_qr_code_file(
            name=name,
            description=description,
            location=location,
            length=length,
            width=width,
            height=height,
        )
        new_bin = Bin(
            user=request.user,
            name=name,
            description=description,
            qr_code=qr_code_file,
            location=location,
            length=length,
            width=width,
            height=height,
        )
        new_bin.save()
        return redirect("home_view")
    return render(request, "core/create_bin.html")

def add_items_to_bin_view(request: HttpRequest) -> render:
    """Handle adding items to a bin.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered add items to bin page or a redirect to the home page.
    """
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("home_view")
    else:
        form = ItemForm(user=request.user)
    return render(request, "core/add_items_to_bin.html", {"form": form})

def list_bins(request: HttpRequest) -> render:
    """List all bins for the current user.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered list bins page.
    """
    bins = Bin.objects.filter(user=request.user)
    return render(request, "core/list_bins.html", {"bins": bins})

def bin_detail(request: HttpRequest, bin_id: int) -> render:
    """Display the details of a specific bin.

    Args:
        request: The HTTP request object.
        bin_id: The ID of the bin.

    Returns:
        The rendered bin detail page.
    """
    _bin = get_object_or_404(Bin, id=bin_id)
    return render(request, "core/bin_detail.html", {"bin": _bin})

def item_detail(request: HttpRequest, item_id: int) -> render:
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
def item_search_view(request: HttpRequest) -> render:
    """Handle item search using LLM.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered search page with results if query provided.
    """
    result = None

    if request.method == "POST":
        form = ItemSearchForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            result = str(find_item_location(query, request.user.id))
    else:
        form = ItemSearchForm()

    return render(request, "core/item_search.html", {
        "form": form,
        "result": result
    })

@login_required
def auto_generate_item_view(request: HttpRequest) -> render:
    """Handle auto-generation of item features from uploaded image.

    This view processes an uploaded image and selected bin to auto-generate
    name and description using LLM, then redirects to confirmation page.

    Args:
        request: The HTTP request object containing image and bin selection.

    Returns:
        The rendered auto-generation page or redirect to confirmation page.
    """
    if request.method == "POST":
        form = AutoGenerateItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            image = form.cleaned_data["image"]
            bin_obj = form.cleaned_data["bin"]
            
            try:
                # Use the item generation function to create the item
                item = get_item_from_img(image.file, bin_obj)
                
                # Store item ID in session for confirmation view
                request.session["generated_item_id"] = item.id
                messages.success(request, "Item features auto-generated successfully!")
                return redirect("confirm_item")
                
            except RuntimeError as e:  # Narrowed example; adjust to specific exceptions raised by get_item_from_img
                messages.error(request, f"Failed to generate item features: {e!s}")
                
    else:
        form = AutoGenerateItemForm(user=request.user)
    
    return render(request, "core/auto_generate_item.html", {"form": form})

@login_required
def confirm_item_view(request: HttpRequest) -> render:
    """Handle confirmation and editing of auto-generated item features.

    This view displays the auto-generated item features (name, description)
    along with the uploaded image and allows the user to edit before saving.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered confirmation page or redirect to add items page after saving.
    """
    # Get the generated item from session
    item_id = request.session.get("generated_item_id")
    if not item_id:
        messages.error(request, "No generated item found. Please start over.")
        return redirect("auto_generate_item")
    
    try:
        item = get_object_or_404(Item, id=item_id, bin__user=request.user)
    except Item.DoesNotExist:
        messages.error(request, "Generated item not found.")
        return redirect("auto_generate_item")
    
    if request.method == "POST":
        form = ConfirmItemForm(request.POST, instance=item, user=request.user)
        if form.is_valid():
            if "confirm" in request.POST:
                # Save the confirmed item
                form.save()
                # Clear session
                if "generated_item_id" in request.session:
                    del request.session["generated_item_id"]
                messages.success(request, f"Item '{item.name}' has been added successfully!")
                return redirect("home_view")
            if "regenerate" in request.POST:
                # Delete the current item and redirect to regenerate
                item.delete()
                if "generated_item_id" in request.session:
                    del request.session["generated_item_id"]
                messages.info(request, "Item deleted. Please upload image again.")
                return redirect("auto_generate_item")
    else:
        form = ConfirmItemForm(instance=item, user=request.user)
    
    return render(request, "core/confirm_item.html", {
        "form": form,
        "item": item
    })


def healthcheck_view(_: HttpRequest) -> JsonResponse:  # pragma: no cover - trivial
    """Lightweight healthcheck endpoint.

    Returns 200 with minimal JSON without hitting database.
    """
    return JsonResponse({"status": "ok"})
