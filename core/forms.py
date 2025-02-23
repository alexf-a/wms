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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['bin'].queryset = Bin.objects.filter(user=user)