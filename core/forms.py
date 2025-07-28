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

class ItemSearchForm(forms.Form):
    """Form for searching items using LLM."""
    
    query = forms.CharField(
        max_length=255, 
        required=True,
        label="",
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Where is my...', 
                'class': 'search-input'
            }
        )
    )

class AutoGenerateItemForm(forms.Form):
    """Form for auto-generating item features from an image."""
    
    image = forms.ImageField(
        required=True,
        label="Upload Item Image",
        help_text="Upload an image of your item to auto-generate name and description"
    )
    bin = forms.ModelChoiceField(
        queryset=Bin.objects.none(),
        required=True,
        label="Select Bin",
        help_text="Choose which bin this item belongs to"
    )
    
    def __init__(self, *args, user=None, **kwargs):
        """Initialize the form with a user-specific queryset for bins.

        Args:
            user (User, optional): The user to filter bins by.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields["bin"].queryset = Bin.objects.filter(user=user)

class ConfirmItemForm(forms.ModelForm):
    """Form for confirming and editing auto-generated item features."""
    
    class Meta:
        model = Item
        fields = ["name", "description", "bin"]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        """Initialize the form with a user-specific queryset for bins.

        Args:
            user (User, optional): The user to filter bins by.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields["bin"].queryset = Bin.objects.filter(user=user)