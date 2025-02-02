from io import BytesIO
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import WMSUserCreationForm
from .models import WMSUser, Bin
from .utils import get_qr_code
import qrcode
from qrcode.image.pil import PilImage
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile

def register_view(request):
    if request.method == 'POST':
        form = WMSUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home_view')
    else:
        form = WMSUserCreationForm()
    return render(request, 'core/auth/register.html', {'form': form})

# I may be able to delete this, and use the built-in LoginView instead
# def login_view(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             login(request, user)
#             return redirect('inventory_view')
#         else:
#             return render(request, 'core/auth/login.html', {'error': 'Invalid username or password'})
#     return render(request, 'core/auth/login.html')

def home_view(request):
    return render(request, 'core/home.html')

@login_required
def inventory_view(request):
    return render(request, 'core/inventory.html')

def expand_inventory_view(request):
    return render(request, 'core/expand_inventory.html')

def create_bin_view(request):
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
        bin = Bin(
            name=name,
            description=description,
            qr_code=qr_code_file,
            location=location,
            length=length,
            width=width,
            height=height
        )
        bin.save()
        return redirect('inventory_view')
    return render(request, 'core/create_bin.html')

def add_items_to_bin_view(request):
    return render(request, 'core/add_items_to_bin.html')
