from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import WMSUserCreationForm, ItemForm
from .models import WMSUser, Bin, Item
from .utils import get_qr_code
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
    if request.method == 'POST':
        form = WMSUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home_view')
    else:
        form = WMSUserCreationForm()
    return render(request, 'core/auth/register.html', {'form': form})

def home_view(request) -> render:
    """Render the home page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered home page.
    """
    return render(request, 'core/home.html')

@login_required
def inventory_view(request) -> render:
    """Render the inventory page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered inventory page.
    """
    return render(request, 'core/inventory.html')

def expand_inventory_view(request) -> render:
    """Render the expand inventory page.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered expand inventory page.
    """
    return render(request, 'core/expand_inventory.html')

def create_bin_view(request) -> render:
    """Handle the creation of a new bin.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered create bin page or a redirect to the inventory page.
    """
    if request.method == 'POST':
        name = request.POST['name']
        description = request.POST['description']
        location = request.POST.get('location', '')
        length = request.POST.get('length', None)
        width = request.POST.get('width', None)
        height = request.POST.get('height', None)

        qr_code: PilImage = get_qr_code(
            name=name,
            description=description,
            location=location,
            length=length,
            width=width,
            height=height
        )
              # Save the QR code to a file-like object
        buffer = BytesIO()
        qr_code.save(buffer, format='PNG')
        file_name = f'{name}_qr.png'
        qr_code_file = ContentFile(buffer.getvalue(), name=file_name)
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
        return redirect('inventory_view')
    return render(request, 'core/create_bin.html')

# File: core/views.py
def add_items_to_bin_view(request) -> render:
    """Handle adding items to a bin.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered add items to bin page or a redirect to the inventory page.
    """
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("inventory_view")
    else:
        form = ItemForm(user=request.user)
    return render(request, 'core/add_items_to_bin.html', {'form': form})

def list_bins(request) -> render:
    """List all bins for the current user.

    Args:
        request: The HTTP request object.

    Returns:
        The rendered list bins page.
    """
    # Fetch all bins for the current user; adjust filtering as needed.
    bins = Bin.objects.filter(user=request.user)
    return render(request, 'core/list_bins.html', {'bins': bins})

def bin_detail(request, bin_id: int) -> render:
    """Display the details of a specific bin.

    Args:
        request: The HTTP request object.
        bin_id: The ID of the bin.

    Returns:
        The rendered bin detail page.
    """
    bin = get_object_or_404(Bin, id=bin_id)
    return render(request, 'core/bin_detail.html', {'bin': bin})

def item_detail(request, item_id: int) -> render:
    """Display the details of a specific item.

    Args:
        request: The HTTP request object.
        item_id: The ID of the item.

    Returns:
        The rendered item detail page.
    """
    item = get_object_or_404(Item, id=item_id)
    return render(request, 'core/item_detail.html', {'item': item})
