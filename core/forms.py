from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Bin, Item, WMSUser


class WMSUserCreationForm(UserCreationForm):
    """Form for creating a new WMSUser."""

    class Meta:
        """Metadata options for WMSUserCreationForm."""

        model = WMSUser
        fields = ("username", "password1", "password2")

class ItemForm(forms.ModelForm):
    """Form for adding or updating an Item."""

    class Meta:
        """Metadata options for ItemForm."""

        model = Item
        fields = ("name", "description", "image", "bin")

    def __init__(self, *args: object, user: WMSUser | None = None, **kwargs: object) -> None:
        """Initialize the form with a user-specific queryset for bins.

        Args:
            *args: Positional arguments passed to the base form.
            user (User, optional): The user to filter bins by.
            **kwargs: Keyword arguments passed to the base form.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields["bin"].queryset = Bin.objects.filter(user=user)

class ItemSearchForm(forms.Form):
    """Form for searching items using LLM."""

    query = forms.CharField(
        max_length=255,
        required=True,
        label="",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Where is my...",
                "class": "search-input"
            }
        )
    )


class AccountForm(forms.ModelForm):
    """Form for updating user account information."""

    class Meta:
        """Metadata options for AccountForm."""

        model = WMSUser
        fields = ("username", "email", "first_name", "last_name")
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
        }
