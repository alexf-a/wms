from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import WMSUser, Item, Bin

class WMSUserCreationForm(UserCreationForm):
    """Form for creating a new WMSUser."""

    class Meta:
        model = WMSUser
        fields = ("username", "password1", "password2")

class ItemForm(forms.ModelForm):
    """Form for adding or updating an Item."""

    class Meta:
        model = Item
        fields = ["name", "description", "image", "bin"]

    def __init__(self, *args, user=None, **kwargs):
        """Initialize the form with a user-specific queryset for bins.

        Args:
            user (User, optional): The user to filter bins by.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields["bin"].queryset = Bin.objects.filter(user=user)