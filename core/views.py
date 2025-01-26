from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .forms import WMSUserCreationForm
from .models import WMSUser

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
