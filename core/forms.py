from __future__ import annotations

from enum import Enum

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Location, Unit, Item, WMSUser


class WMSUserAuthForm(forms.Form):
    """Authentication form that uses email instead of username."""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
            'autofocus': True,
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password'
        })
    )
    
    error_messages = {
        'invalid_login': "Please enter a correct email and password.",
        'inactive': "This account is inactive.",
    }
    
    def __init__(self, request=None, *args, **kwargs):
        """Initialize form with request object for authentication."""
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate email and password."""
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        
        if email is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=email,  # Backend expects 'username' parameter
                password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    self.error_messages['inactive'],
                    code='inactive',
                )
        return self.cleaned_data
    
    def get_user(self):
        """Return authenticated user."""
        return self.user_cache


# Storage type constants
STORAGE_TYPE_LOCATION = 'location'
STORAGE_TYPE_UNIT = 'unit'
STORAGE_TYPE_CHOICES = [
    (STORAGE_TYPE_LOCATION, 'No - this is a location for storage units (eg. A house, a facility)'),
    (STORAGE_TYPE_UNIT, 'Yes - this is a storage unit (eg. a bin, a locker, etc.)'),
]


class ContainerType(Enum):
    """Enum for container types based on prefixed ID format."""
    LOCATION = 'location'
    UNIT = 'unit'


def parse_container_string(container_string: str) -> tuple[ContainerType, int]:
    """Parse container string into type and ID.
    
    Args:
        container_string: Non-empty container string in format '<type>_<id>' where type
            matches ContainerType enum values ('location' or 'unit').
    
    Returns:
        Tuple of (ContainerType, id).
    
    Raises:
        ValidationError: If container format is invalid or empty.
    
    Examples:
        >>> parse_container_string('location_123')
        (ContainerType.LOCATION, 123)
        >>> parse_container_string('unit_456')
        (ContainerType.UNIT, 456)
    """
    if not container_string:
        raise ValidationError("Container cannot be empty")
    
    try:
        prefix, id_str = container_string.split('_', 1)
        container_type = ContainerType(prefix)
        container_id = int(id_str)
    except ValueError as e:
        raise ValidationError(f"Invalid container format: {container_string}") from e
    except (IndexError, AttributeError) as e:
        raise ValidationError(f"Invalid container ID format: {container_string}") from e
    
    return container_type, container_id


def build_container_choices(user: WMSUser, exclude_unit: Unit | None = None) -> list[tuple[str, str]]:
    """Build container choices for Location and Unit dropdowns.
    
    Args:
        user: The user to filter containers for.
        exclude_unit: Optional Unit instance to exclude (along with its descendants).
    
    Returns:
        List of (value, label) tuples for the dropdown choices.
    """
    container_choices = [('', '--- None (standalone) ---')]
    
    # Add locations with 📍 prefix
    locations = Location.objects.filter(user=user).order_by('name')
    for loc in locations:
        container_choices.append((f'{ContainerType.LOCATION.value}_{loc.id}', f'📍 {loc.name}'))
    
    # Add units with 📦 prefix
    units = Unit.objects.filter(user=user).order_by('name')
    
    # Build exclusion set if editing a unit
    excluded_ids = set()
    if exclude_unit:
        excluded_ids.add(exclude_unit.id)
        # Exclude all descendants to prevent circular references
        excluded_ids.update(unit.id for unit in exclude_unit.get_descendants())
    
    for unit in units:
        if unit.id not in excluded_ids:
            container_choices.append((f'{ContainerType.UNIT.value}_{unit.id}', f'📦 {unit.name}'))
    
    return container_choices


class WMSUserCreationForm(UserCreationForm):
    """Form for creating a new WMSUser with email-based authentication."""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email address',
            'autocomplete': 'email'
        })
    )

    class Meta:
        """Metadata options for WMSUserCreationForm."""

        model = WMSUser
        fields = ("email", "password1", "password2")


class StorageSpaceForm(forms.Form):
    """Unified form for creating either a Location or Unit.
    
    Uses a radio button to determine if the space stores items directly (Unit)
    or is purely organizational (Location).
    """
    
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., Garage, Red Toolbox'})
    )
    
    stores_items = forms.ChoiceField(
        choices=STORAGE_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial=STORAGE_TYPE_LOCATION,
        label='Will you store items directly in this space?'
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'placeholder': 'Optional description', 'rows': 3})
    )
    
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Optional address (for locations only)',
            'rows': 2
        }),
        help_text='Only applicable for storage locations.'
    )
    
    # Unit-specific fields (shown conditionally via JavaScript)
    container = forms.ChoiceField(
        required=False,
        label='Container (optional)',
        help_text='Select a location or parent unit'
    )
    
    length = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Length in inches'}),
        label='Length (inches)'
    )
    
    width = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Width in inches'}),
        label='Width (inches)'
    )
    
    height = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Height in inches'}),
        label='Height (inches)'
    )
    
    def __init__(self, *args: object, user: WMSUser | None = None, **kwargs: object) -> None:
        """Initialize form with user-specific container choices.
        
        Args:
            user: The user to filter containers for.
        """
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['container'].choices = build_container_choices(user)
            self.user = user
        else:
            self.user = None
    
    def clean_name(self) -> str:
        """Validate that name doesn't collide with existing Location or Unit names."""
        name = self.cleaned_data.get('name')
        
        if self.user and name:
            # Check for collisions with existing Locations
            if Location.objects.filter(user=self.user, name=name).exists():
                raise ValidationError(
                    f'A location named "{name}" already exists. Please choose a different name.'
                )
            
            # Check for collisions with existing Units
            if Unit.objects.filter(user=self.user, name=name).exists():
                raise ValidationError(
                    f'A unit named "{name}" already exists. Please choose a different name.'
                )
        
        return name
    
    def clean(self) -> dict:
        """Validate container selection and dimensions."""
        cleaned_data = super().clean()
        stores_items = cleaned_data.get('stores_items')
        
        # If storing items (Unit), validate container reference
        if stores_items == STORAGE_TYPE_UNIT:
            container = cleaned_data.get('container')
            if container:
                # Validate container format (will raise ValidationError if invalid)
                try:
                    parse_container_string(container)
                except ValidationError:
                    raise
        
        return cleaned_data
    
    def save(self) -> Location | Unit:
        """Create and return either a Location or Unit based on stores_items choice.
        
        Returns:
            The created Location or Unit instance.
        
        Raises:
            ValueError: If form hasn't been validated or user is missing.
        """
        if not self.is_valid():
            raise ValueError("Form must be validated before saving")
        
        if not self.user:
            raise ValueError("User is required to save the form")
        
        stores_items = self.cleaned_data['stores_items']
        name = self.cleaned_data['name']
        description = self.cleaned_data.get('description')
        
        if stores_items == STORAGE_TYPE_LOCATION:
            # Create Location
            location = Location.objects.create(
                user=self.user,
                name=name,
                description=description,
                address=self.cleaned_data.get('address')
            )
            return location
        else:
            # Create Unit
            container = self.cleaned_data.get('container')
            
            unit = Unit(
                user=self.user,
                name=name,
                description=description,
                length=self.cleaned_data.get('length'),
                width=self.cleaned_data.get('width'),
                height=self.cleaned_data.get('height')
            )
            
            # Set container relationship
            if container:
                container_type, container_id = parse_container_string(container)
                
                if container_type == ContainerType.LOCATION:
                    unit.location_id = container_id
                elif container_type == ContainerType.UNIT:
                    unit.parent_unit_id = container_id
            
            unit.save()
            return unit


class UnitForm(forms.ModelForm):
    """Form for creating or updating a Unit with container selection."""
    
    container = forms.ChoiceField(
        required=False,
        label='Container',
        help_text='Select a location or parent unit (optional)'
    )
    
    class Meta:
        """Metadata options for UnitForm."""
        
        model = Unit
        fields = ('name', 'description', 'length', 'width', 'height')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'length': forms.NumberInput(attrs={'placeholder': 'inches'}),
            'width': forms.NumberInput(attrs={'placeholder': 'inches'}),
            'height': forms.NumberInput(attrs={'placeholder': 'inches'}),
        }
    
    def __init__(self, *args: object, user: WMSUser | None = None, instance: Unit | None = None, **kwargs: object) -> None:
        """Initialize form with user-specific container choices.
        
        Args:
            user: The user to filter containers for.
            instance: The Unit instance being edited (if any).
        """
        super().__init__(*args, instance=instance, **kwargs)
        
        self.user = user
        self.instance = instance
        
        if user:
            self.fields['container'].choices = build_container_choices(user, exclude_unit=instance)
            
            # Set initial container value if editing
            if instance:
                if instance.location:
                    self.initial['container'] = f'{ContainerType.LOCATION.value}_{instance.location.id}'
                elif instance.parent_unit:
                    self.initial['container'] = f'{ContainerType.UNIT.value}_{instance.parent_unit.id}'
    
    def clean_name(self) -> str:
        """Validate name doesn't collide with other units or locations."""
        name = self.cleaned_data.get('name')
        
        if self.user and name:
            # Check Location collisions
            if Location.objects.filter(user=self.user, name=name).exists():
                raise ValidationError(
                    f'A location named "{name}" already exists. Please choose a different name.'
                )
            
            # Check Unit collisions (excluding self if editing)
            unit_query = Unit.objects.filter(user=self.user, name=name)
            if self.instance and self.instance.id:
                unit_query = unit_query.exclude(id=self.instance.id)
            
            if unit_query.exists():
                raise ValidationError(
                    f'A unit named "{name}" already exists. Please choose a different name.'
                )
        
        return name
    
    def save(self, commit: bool = True) -> Unit:
        """Save the unit with the selected container."""
        unit = super().save(commit=False)
        
        # Parse container selection (convert empty string to None)
        container = self.cleaned_data.get('container') or None
        
        if container:
            container_type, container_id = parse_container_string(container)
            
            if container_type == ContainerType.LOCATION:
                # Set location FK
                unit.location_id = container_id
                unit.parent_unit = None
            elif container_type == ContainerType.UNIT:
                # Set parent_unit FK
                unit.parent_unit_id = container_id
                unit.location = None
        else:
            # Standalone unit
            unit.location = None
            unit.parent_unit = None
        
        if commit:
            unit.save()
        
        return unit


class ItemForm(forms.ModelForm):
    """Form for adding or updating an Item."""

    class Meta:
        """Metadata options for ItemForm."""

        model = Item
        fields = ("name", "description", "image", "unit")

    def __init__(self, *args: object, user: WMSUser | None = None, **kwargs: object) -> None:
        """Initialize the form with a user-specific queryset for units.

        Args:
            *args: Positional arguments passed to the base form.
            user (User, optional): The user to filter units by.
            **kwargs: Keyword arguments passed to the base form.
        """
        super().__init__(*args, **kwargs)
        if user:
            self.fields["unit"].queryset = Unit.objects.filter(user=user)

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
        fields = ("email", "first_name", "last_name")
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
        }
