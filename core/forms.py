from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import WMSUser, Item, Bin

class WMSUserCreationForm(UserCreationForm):
    class Meta:
        model = WMSUser
        fields = ('username', 'password1', 'password2')

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'image', 'bin']