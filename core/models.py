from __future__ import annotations

import base64
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils.text import slugify

from schemas import ItemSearchInput

from .upload_paths import user_item_image_upload_path
from .utils import generate_unit_access_token, get_qr_code_file


class WMSUserManager(BaseUserManager):
    """Custom manager for WMSUser that uses email as the username field."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class WMSUser(AbstractUser):
    """Custom user model with email as primary identifier instead of username.
    
    Username is optional and not required for authentication.
    Email is required, unique, and used for login.
    """

    # Make username optional
    username = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Optional display name"
    )

    # Make email required and unique
    email = models.EmailField(
        unique=True,
        blank=False,
        null=False,
        help_text="Required. Used for authentication."
    )

    # Force password change on first login (for beta users)
    must_change_password = models.BooleanField(
        default=False,
        help_text="If True, user will be required to change password on next login."
    )

    # Onboarding wizard completion
    has_completed_onboarding = models.BooleanField(
        default=False,
        help_text="If True, user has completed the onboarding wizard."
    )

    # Use email as the username field for authentication
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email is already the USERNAME_FIELD, so don't include it here

    objects = WMSUserManager()

    class Meta:
        """Metadata for the WMSUser model."""

        app_label: ClassVar[str] = "core"

    def accessible_units(self) -> QuerySet[Unit]:
        """Return all units this user owns or has explicit shared access to.

        Includes only units accessible via direct UnitSharedAccess.
        LocationSharedAccess grants visibility of unit names within the
        location but does NOT grant access to unit contents.

        Returns:
            QuerySet of Unit objects this user can access.
        """
        return Unit.objects.filter(
            Q(user=self)
            | Q(unitsharedaccess__user=self)
        ).distinct()

    def writable_units(self) -> QuerySet[Unit]:
        """Return all units this user owns or has write access to.

        Excludes units shared with read-only permission.

        Returns:
            QuerySet of Unit objects this user can write to.
        """
        return Unit.objects.filter(
            Q(user=self)
            | Q(
                unitsharedaccess__user=self,
                unitsharedaccess__permission__in=[
                    Permission.WRITE,
                    Permission.WRITE_ALL,
                ],
            )
        ).distinct()

    def accessible_locations(self) -> QuerySet[Location]:
        """Return all locations this user owns or has shared access to.

        Returns:
            QuerySet of Location objects this user can access.
        """
        return Location.objects.filter(
            Q(user=self) | Q(shared_access__user=self)
        ).distinct()

    def accessible_items(self) -> QuerySet[Item]:
        """Return all items this user owns or can see via explicit unit sharing.

        Only includes items in units with direct UnitSharedAccess.
        LocationSharedAccess does NOT grant access to items within units.

        Returns:
            QuerySet of Item objects this user can access.
        """
        return Item.objects.filter(
            Q(user=self)
            | Q(unit__unitsharedaccess__user=self)
        ).distinct()


class StorageSpace(models.Model):
    """Abstract base class for storage containers.
    
    Provides common fields and behavior for both Locations and Units.
    Never instantiated directly - only used as a base class.
    
    Attributes:
        user (User): The owner of the storage space.
        name (str): The name of the storage space.
        description (str): Additional details about the storage space.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        """Mark this as an abstract base class."""

        abstract = True

    def __str__(self) -> str:
        return self.name


class Location(StorageSpace):
    """Organizational location (address, building, room).

    Pure metadata - does not contain items directly. Items must be in Units.

    Attributes:
        user (User): Inherited from StorageSpace.
        name (str): Inherited from StorageSpace.
        description (str): Inherited from StorageSpace.
        address (str): Physical address (optional).
        shared_users (ManyToManyField): Users with shared access to the location.
    """
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="LocationSharedAccess",
        blank=True,
        related_name="shared_locations"
    )
    address = models.TextField(blank=True, null=True)

    class Meta:
        """Model constraints for Location."""

        unique_together: ClassVar = ("user", "name")

    def can_promote_to_unit(self) -> bool:
        """Check if this Location can be safely promoted to a Unit.
        
        Locations can always be promoted. If they have child Units, those Units
        will be reassigned to have the new Unit as their parent.
        
        Returns:
            bool: Always True.
        """
        return True

    def promote_to_unit(self) -> Unit:
        """Convert this Location into a Unit.
        
        This is useful when a user realizes they want to store items directly
        in what they originally thought was just a Location (e.g., adding a 
        leaf blower directly to a "Garage" that already contains other Units).
        
        The Location is deleted and replaced with a Unit of the same name.
        All child Units that referenced this Location will be updated to 
        reference the new Unit as their parent_unit instead.
        
        Returns:
            Unit: The newly created Unit instance.
        """
        # Create the Unit with the same name and description
        unit = Unit.objects.create(
            user=self.user,
            name=self.name,
            description=self.description,
            location=None,
            parent_unit=None
        )

        # Reassign all child Units from this Location to the new Unit
        # Change their location FK to None and set parent_unit to the new Unit
        self.unit_set.all().update(location=None, parent_unit=unit)

        # Delete the Location
        self.delete()

        return unit

    def get_user_permission(self, user: WMSUser) -> Permission | None:
        """Return the effective permission level for a user on this Location.

        Args:
            user: The user to check.

        Returns:
            Permission member for the user, or None if no access.
        """
        if self.user_id == user.id:
            return Permission.OWNER
        access = LocationSharedAccess.objects.filter(
            user=user, location=self
        ).first()
        return Permission(access.permission) if access else None


class Permission(StrEnum):
    """Sharing permission levels — single source of truth.

    ``OWNER`` is computed at runtime (never stored in the database).
    ``READ``, ``WRITE``, and ``WRITE_ALL`` are the storable permission levels.
    """

    OWNER = "owner"
    READ = "read"
    WRITE = "write"
    WRITE_ALL = "write_all"

    @classmethod
    def storable(cls) -> tuple[Permission, ...]:
        """Return the permission levels that can be stored in the database.

        Excludes ``OWNER`` which is computed, not stored.
        """
        return (cls.READ, cls.WRITE, cls.WRITE_ALL)


class LocationSharedAccess(models.Model):
    """Model to handle shared access to locations with specific permissions.

    Access to a Location grants visibility of Unit names within it and
    the ability to create new Units (with write permission). It does NOT
    grant access to Unit contents (items, child units). Explicit
    UnitSharedAccess is required for that.

    Attributes:
        user (User): The user with shared access.
        location (Location): The location to which access is shared.
        permission (str): The level of permission (e.g., "read", "write").
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, related_name="shared_access", on_delete=models.CASCADE)
    permission = models.CharField(
        max_length=50,
        default=Permission.READ,
        choices={p.value: p.value for p in Permission.storable()},
    )

    class Meta:
        """Model constraints for shared location access."""

        unique_together: ClassVar = ("user", "location")
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(permission__in=[p.value for p in Permission.storable()]),
                name="locationsharedaccess_valid_permission",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} → {self.location.name} ({self.permission})"


# Dimension unit choices
DIMENSION_UNIT_CHOICES = [
    ("in", "Inches"),
    ("cm", "Centimeters"),
    ("ft", "Feet"),
    ("m", "Meters"),
]

# Quantity units - single source of truth
ITEM_QUANTITY_MAX_DIGITS = 10
ITEM_QUANTITY_DECIMAL_PLACES = 2
ITEM_QUANTITY_COUNT_STEP = Decimal("1")
ITEM_QUANTITY_NON_COUNT_STEP = Decimal("0.1")
# Rounding quantum for non-count quantities (e.g., 0.01 for 2 decimal places)
ITEM_QUANTITY_ROUNDING_QUANTUM = Decimal(10) ** -ITEM_QUANTITY_DECIMAL_PLACES

# Map unit symbol to display name
UNIT_2_NAME = {
    "count": "Count",
    "mg": "Milligrams",
    "g": "Grams",
    "kg": "Kilograms",
    "oz": "Ounces",
    "lb": "Pounds",
    "mL": "Milliliters",
    "L": "Liters",
    "fl_oz": "Fluid Ounces",
    "gal": "Gallons",
    "mm": "Millimeters",
    "cm": "Centimeters",
    "m": "Meters",
    "in": "Inches",
    "ft": "Feet",
}

# Map category to set of unit symbols
CATEGORY_2_UNITS: dict[str, tuple[str]] = {
    "count": ("count",),
    "mass": ("mg", "g", "kg", "oz", "lb"),
    "volume": ("mL", "L", "fl_oz", "gal"),
    "length": ("mm", "cm", "m", "in", "ft"),
}

#: Radio options for quantity categories.
#:
#: Examples:
#: - ("count", "Count")
#: - ("mass", "Mass")
QUANTITY_CATEGORY_CHOICES: list[tuple[str, str]] = [
    (category, category.capitalize())
    for category in CATEGORY_2_UNITS
]

#: Grouped unit choices for Django model fields.
#:
#: Examples:
#: - ("Count", [("count", "Count")])
#: - ("Mass", [("g", "Grams"), ("kg", "Kilograms")])
QUANTITY_UNIT_CHOICES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        category.capitalize(),
        [(unit, UNIT_2_NAME[unit]) for unit in sorted(units)],
    )
    for category, units in sorted(CATEGORY_2_UNITS.items())
]
#: Reverse lookup from unit symbol to quantity category.
#:
#: Examples:
#: - "kg" -> "mass"
#: - "mL" -> "volume"
CATEGORY_BY_UNIT: dict[str, str] = {}
for category, units in CATEGORY_2_UNITS.items():
    for unit in units:
        CATEGORY_BY_UNIT[unit] = category


class Unit(StorageSpace):
    """Generic storage unit (bin, locker, garage, van, shelf, workbench, etc.).
    
    Can exist standalone or within a Location. Can be nested within another Unit.
    
    Attributes:
        user (User): Inherited from StorageSpace.
        name (str): Inherited from StorageSpace.
        description (str): Inherited from StorageSpace.
        shared_users (ManyToManyField): Users with shared access to the unit.
        location (Location): Location containing this unit (if top-level).
        parent_unit (Unit): Parent unit containing this unit (if nested).
        length (float): The length of the unit in inches.
        width (float): The width of the unit in inches.
        height (float): The height of the unit in inches.
        access_token (str): Unique token for QR code access.
    """
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="UnitSharedAccess",
        blank=True,
        related_name="shared_units"
    )

    # Parent can be either a Location OR another Unit (but not both)
    location = models.ForeignKey(
        Location,
        related_name="unit_set",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Location containing this unit (if top-level)"
    )

    parent_unit = models.ForeignKey(
        "self",
        related_name="child_units",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Parent unit containing this unit (if nested)"
    )

    # Physical properties
    length = models.FloatField(blank=True, null=True, help_text="Length dimension")
    width = models.FloatField(blank=True, null=True, help_text="Width dimension")
    height = models.FloatField(blank=True, null=True, help_text="Height dimension")
    dimensions_unit = models.CharField(
        max_length=2,
        choices=DIMENSION_UNIT_CHOICES,
        blank=True,
        null=True,
        help_text="Unit of measurement for dimensions"
    )

    # QR code support
    access_token = models.CharField(
        max_length=48,
        unique=True,
        default=generate_unit_access_token
    )

    class Meta:
        """Model constraints for Unit."""

        unique_together: ClassVar = ("user", "name")
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=(
                    models.Q(location__isnull=True, parent_unit__isnull=False) |
                    models.Q(location__isnull=False, parent_unit__isnull=True) |
                    models.Q(location__isnull=True, parent_unit__isnull=True)
                ),
                name="unit_has_location_or_parent_not_both"
            ),
            models.CheckConstraint(
                condition=(
                    # All dimensions NULL (no dimensions provided)
                    models.Q(
                        length__isnull=True,
                        width__isnull=True,
                        height__isnull=True,
                        dimensions_unit__isnull=True
                    ) |
                    # All dimensions NOT NULL (complete dimensions with unit)
                    models.Q(
                        length__isnull=False,
                        width__isnull=False,
                        height__isnull=False,
                        dimensions_unit__isnull=False
                    )
                ),
                name="unit_dimensions_all_or_nothing"
            )
        ]

    def get_container(self) -> Location | Unit | None:
        """Return the parent container (either Location or parent Unit).
        
        Returns:
            Location | Unit | None: The Location or parent Unit containing this Unit,
                or None if standalone.
        """
        return self.location or self.parent_unit

    @property
    def parent(self) -> Location | Unit | None:
        """Return the parent container (either Location or parent Unit).
        
        This property simplifies hierarchy traversal by providing a single
        interface to access either the location or parent_unit.
        
        Returns:
            Location | Unit | None: The Location or parent Unit containing this Unit,
                or None if standalone.
        """
        return self.location or self.parent_unit

    def get_full_path(self) -> str:
        """Return hierarchical path from root to this unit.
        
        Walks up the parent chain, including both Units and Locations.
        
        Examples:
            - "Garage > Workbench > Red Toolbox"
            - "Storage Unit A > Shelf 3 > Blue Bin"
            - "Work Van" (standalone, no parent)
        
        Returns:
            str: Human-readable path string with " > " separators.
        """
        parts = []
        current: Location | Unit | None = self

        # Walk up the entire hierarchy (Units and Location)
        while current:
            parts.insert(0, current.name)
            current = current.parent if isinstance(current, Unit) else None

        return " > ".join(parts)

    def get_ancestor_path(self) -> str:
        """Return hierarchical path from root to this unit's parent (excludes self).

        Useful when the unit name is already displayed separately (e.g., as a heading)
        and only the ancestor context is needed.

        Examples:
            - "Garage > Workbench" (for a unit nested under Workbench)
            - "Garage" (for a top-level unit in a location)
            - "" (standalone unit with no parent)

        Returns:
            str: Ancestor path with " > " separators, or empty string if no parent.
        """
        full = self.get_full_path()
        # Remove the last segment (self.name)
        sep = " > "
        idx = full.rfind(sep)
        return full[:idx] if idx != -1 else ""

    def get_root_unit(self) -> Unit:
        """Return the top-level Unit in this hierarchy.
        
        Returns:
            Unit: The root Unit (the one with no parent_unit).
        """
        current = self
        while isinstance(current.parent, Unit):
            current = current.parent
        return current

    def get_ancestors(self) -> list[Location | Unit]:
        """Return list of all ancestors from root to self.
        
        Includes the full hierarchy from root Location (if any) through all 
        parent Units to self.
        
        Returns:
            list[Location | Unit]: List ordered from root to leaf, e.g.,
                [<Location: My House>, <Unit: Garage>, <Unit: Workbench>, <Unit: Red Toolbox>]
        """
        ancestors = []
        current: Location | Unit | None = self

        # Walk up the entire hierarchy including Location
        while current:
            ancestors.insert(0, current)
            current = current.parent if isinstance(current, Unit) else None

        return ancestors

    def get_descendants(self) -> list[Unit]:
        """Return all descendant Units (children, grandchildren, etc.).
        
        Used to prevent circular references when editing Unit hierarchy.
        
        Returns:
            list[Unit]: All Units nested within this Unit.
        """
        descendants = []
        for child in self.child_units.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def has_children(self) -> bool:
        """Check if this Unit has any child Units.
        
        Returns:
            bool: True if this Unit contains other Units, False otherwise.
        """
        return self.child_units.exists()

    def user_has_access(self, user: WMSUser) -> bool:
        """Check if a user has access to this Unit.

        Checks:
        1. Direct ownership
        2. Direct UnitSharedAccess for this Unit

        Note: Access does NOT inherit from parent Units or Locations.
        LocationSharedAccess grants visibility of unit names but not
        access to unit contents. Sharing must be explicit per unit.

        Args:
            user: The user to check access for.

        Returns:
            bool: True if user is owner or has shared access, False otherwise.
        """
        # Owner always has access
        if self.user_id == user.id:
            return True

        # Check direct unit access
        if UnitSharedAccess.objects.filter(user=user, unit=self).exists():
            return True

        return False

    def get_user_permission(self, user: WMSUser) -> Permission | None:
        """Return the effective permission level for a user on this Unit.

        Checks ownership and direct UnitSharedAccess only.
        LocationSharedAccess does NOT grant unit-level permissions.

        Args:
            user: The user to check.

        Returns:
            Permission member for the user, or None if no access.
        """
        if self.user_id == user.id:
            return Permission.OWNER

        # Check direct unit access
        access = UnitSharedAccess.objects.filter(user=user, unit=self).first()
        if access:
            return Permission(access.permission)

        return None

    def get_qr_filename(self) -> str:
        """Return a deterministic filename for the unit's QR code image."""
        return f"{slugify(self.name) or 'unit'}_unit_qr.png"

    def get_detail_path(self) -> str:
        """Return the relative URL path to this unit's detail view."""
        return reverse(
            "unit_detail",
            kwargs={"user_id": self.user_id, "access_token": self.access_token},
        )

    def get_qr_code(self, *, base_url: str) -> ContentFile:
        """Generate a QR code file pointing to this unit's detail view.
        
        Args:
            base_url: The absolute base URL of the site (e.g., "https://app.example.com/").
        
        Returns:
            ContentFile: An in-memory QR code image for the unit.
        """
        normalized_base = base_url.rstrip("/") + "/"
        detail_url = urljoin(normalized_base, self.get_detail_path().lstrip("/"))
        return get_qr_code_file(detail_url, filename=self.get_qr_filename())


class UnitSharedAccess(models.Model):
    """Model to handle shared access to units with specific permissions.

    Attributes:
        user (User): The user with shared access.
        unit (Unit): The unit to which access is shared.
        permission (str): The level of permission — ``"read"`` (view only),
            ``"write"`` (CRUD own items), or ``"write_all"`` (CRUD any item).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    permission = models.CharField(
        max_length=50,
        default=Permission.READ,
        choices={p.value: p.value for p in Permission.storable()},
    )

    class Meta:
        """Model constraints for shared unit access."""

        unique_together: ClassVar = ("user", "unit")
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(permission__in=[p.value for p in Permission.storable()]),
                name="unitsharedaccess_valid_permission",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} → {self.unit.name} ({self.permission})"


class Item(models.Model):
    """Model representing an item stored in a unit.
    
    Attributes:
        user (User): The owner of the item.
        name (str): The name of the item.
        description (str): A description of the item.
        created_on (DateTimeField): The date and time the item was created.
        image (ImageField): An optional image of the item.
        unit (Unit): The unit in which the item is stored.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="items", on_delete=models.CASCADE, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=user_item_image_upload_path, blank=True, null=True)
    unit = models.ForeignKey(Unit, related_name="items", on_delete=models.CASCADE)

    # Quantity tracking (optional)
    quantity = models.DecimalField(
        max_digits=ITEM_QUANTITY_MAX_DIGITS,
        decimal_places=ITEM_QUANTITY_DECIMAL_PLACES,
        blank=True,
        null=True,
        help_text="Amount of this item",
    )
    quantity_unit = models.CharField(
        max_length=10,
        choices=QUANTITY_UNIT_CHOICES,
        blank=True,
        default="",
        help_text="Unit of measurement for quantity"
    )

    class Meta:
        """Model constraints for Item."""

        unique_together: ClassVar = ("user", "name")
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=(
                    models.Q(quantity__isnull=True, quantity_unit="") |
                    models.Q(quantity__isnull=False) & ~models.Q(quantity_unit="")
                ),
                name="item_quantity_all_or_nothing"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(quantity__gte=0),
                name="item_quantity_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the item after verifying the user has write access to the unit."""
        if self.unit is None:
            msg = f"Must assign a Unit before saving Item {self}"
            raise ValueError(msg)
        if self.user is None:
            self.user = self.unit.user
        elif self.user_id != self.unit.user_id:
            # Require write-level permission for shared users to mutate items
            perm = self.unit.get_user_permission(self.user)
            if perm is None or perm == Permission.READ:
                msg = f"User {self.user} does not have write access to Unit {self.unit}"
                raise ValueError(msg)

        super().save(*args, **kwargs)

    @property
    def formatted_quantity(self) -> str | None:
        """Return formatted quantity string or None.

        Returns:
            str | None: Formatted quantity like "5 kg" or "100 count", or None if no quantity set.
        """
        if self.quantity is not None and self.quantity_unit:
            # Get the display name for the unit
            unit_display = UNIT_2_NAME.get(self.quantity_unit, self.quantity_unit)
            # Format as integer for count, two decimals for others
            formatted_value = (
                int(self.quantity)
                if self.quantity_unit == "count"
                else self.quantity.quantize(Decimal("0.01"))
            )
            return f"{formatted_value} {unit_display.lower()}"
        return None

    def to_search_input(self) -> ItemSearchInput:
        """Convert this Item instance to an ItemSearchInput for LLM search.

        Returns:
            ItemSearchInput: A Pydantic model with item data ready for LLM search
        """
        image = None

        # If item has an image, encode it to base64
        if self.image:
            try:
                with self.image.open("rb") as image_file:
                    image_data = image_file.read()
                    image = base64.b64encode(image_data).decode("utf-8")
            except (FileNotFoundError, AttributeError, OSError, ValueError):
                # If image file can't be accessed or read, skip it
                pass

        return ItemSearchInput(
            name=self.name,
            description=self.description,
            unit_name=self.unit.name,
            image=image
        )

