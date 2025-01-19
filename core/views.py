from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import WMSUserCreationForm
from .models import WMSUser

def register(request):
    if request.method == 'POST':
        form = WMSUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = WMSUserCreationForm()
    return render(request, 'core/auth/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'core/auth/login.html', {'error': 'Invalid username or password'})
    return render(request, 'core/auth/login.html')

def home(request):
    return render(request, 'core/home.html')
