from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import WMSUserCreationForm, ItemForm, ItemSearchForm
from .models import WMSUser, Bin, Item
from .utils import get_qr_code_file
from llm.llm_search import find_item_location
import qrcode
from qrcode.image.pil import PilImage
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile

def register_view(request) -> render:
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
            return redirect("home_view")
    else:
        form = WMSUserCreationForm()
    return render(request, "core/auth/register.html", {"form": form})

def home_view(request) -> render:
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

        qr_code_file: ContentFile = get_qr_code_file(
            name=name,
            description=description,
            location=location,
            length=length,
            width=width,
            height=height
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
            query = form.cleaned_data['query']
            result = str(find_item_location(query, request.user.id))
    else:
        form = ItemSearchForm()

    return render(request, "core/item_search.html", {
        "form": form,
        "result": result
    })
