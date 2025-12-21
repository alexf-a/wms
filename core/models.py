from __future__ import annotations
import base64
from typing import ClassVar
from urllib.parse import urljoin

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from schemas import ItemSearchInput

from .upload_paths import user_item_image_upload_path
from .utils import generate_unit_access_token, get_qr_code_file


class WMSUser(User):
    """Custom user model extending Django's built-in User model."""

    class Meta:
        """Metadata for the WMSUser proxy."""

        app_label: ClassVar[str] = "core"


class Location(models.Model):
    """Organizational location (address, building, room).
    
    Pure metadata - does not contain items directly. Items must be in Units.
    
    Attributes:
        user (User): The owner of the location.
        name (str): The name of the location (e.g., "My House", "Storage Facility A").
        address (str): Physical address (optional).
        description (str): Additional details about the location.
    """
    user = models.ForeignKey(User, related_name="locations", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        """Model constraints for Location."""
        
        unique_together: ClassVar = ("user", "name")
    
    def __str__(self) -> str:
        return self.name
    
    def can_promote_to_unit(self) -> bool:
        """Check if this Location can be safely promoted to a Unit.
        
        Locations can always be promoted. If they have child Units, those Units
        will be reassigned to have the new Unit as their parent.
        
        Returns:
            bool: Always True.
        """
        return True
    
    def promote_to_unit(self) -> "Unit":
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
        self.units.all().update(location=None, parent_unit=unit)
        
        # Delete the Location
        self.delete()
        
        return unit


class LocationSharedAccess(models.Model):
    """Model to handle shared access to locations with specific permissions.
    
    Access to a Location grants transitive access to all Units within it.
    
    Attributes:
        user (User): The user with shared access.
        location (Location): The location to which access is shared.
        permission (str): The level of permission (e.g., "read", "write").
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    permission = models.CharField(max_length=50, default="read")

    class Meta:
        """Model constraints for shared location access."""

        unique_together: ClassVar = ("user", "location")

    def __str__(self) -> str:
        return f"{self.user.username} → {self.location.name} ({self.permission})"


class Unit(models.Model):
    """Generic storage unit (bin, locker, garage, van, shelf, workbench, etc.).
    
    Can exist standalone or within a Location. Can be nested within another Unit.
    
    Attributes:
        user (User): The primary owner of the unit.
        shared_users (ManyToManyField): Users with shared access to the unit.
        name (str): The name of the unit.
        description (str): A description of the unit.
        location (Location): Location containing this unit (if top-level).
        parent_unit (Unit): Parent unit containing this unit (if nested).
        length (float): The length of the unit in inches.
        width (float): The width of the unit in inches.
        height (float): The height of the unit in inches.
        access_token (str): Unique token for QR code access.
    """
    user = models.ForeignKey(User, related_name="units", on_delete=models.CASCADE)
    shared_users = models.ManyToManyField(
        User,
        through="UnitSharedAccess",
        blank=True,
        related_name="shared_units"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Parent can be either a Location OR another Unit (but not both)
    location = models.ForeignKey(
        Location,
        related_name="units",
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
    length = models.FloatField(blank=True, null=True, help_text="in inches")
    width = models.FloatField(blank=True, null=True, help_text="in inches")
    height = models.FloatField(blank=True, null=True, help_text="in inches")
    
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
            )
        ]
    
    def __str__(self) -> str:
        return self.name
    
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
    
    def get_root_unit(self) -> "Unit":
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
    
    def get_descendants(self) -> list["Unit"]:
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
    
    def user_has_access(self, user: User) -> bool:
        """Check if a user has access to this Unit.
        
        Checks:
        1. Direct ownership
        2. Direct UnitSharedAccess for this Unit
        3. Transitive UnitSharedAccess through any parent Unit
        4. Transitive LocationSharedAccess through root Location
        
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
        
        # Check transitive access through parent hierarchy
        current = self.parent
        while current:
            if isinstance(current, Unit):
                if UnitSharedAccess.objects.filter(user=user, unit=current).exists():
                    return True
            elif isinstance(current, Location):
                if LocationSharedAccess.objects.filter(user=user, location=current).exists():
                    return True
            current = current.parent if isinstance(current, Unit) else None
        
        return False
    
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
        permission (str): The level of permission (e.g., "read", "write").
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    permission = models.CharField(max_length=50, default="read")

    class Meta:
        """Model constraints for shared unit access."""

        unique_together: ClassVar = ("user", "unit")

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
    user = models.ForeignKey(User, related_name="items", on_delete=models.CASCADE, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=user_item_image_upload_path, blank=True, null=True)
    unit = models.ForeignKey(Unit, related_name="items", on_delete=models.CASCADE)

    class Meta:
        """Model constraints for Item."""

        unique_together: ClassVar = ("user", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the item after verifying ownership alignment."""
        if self.unit is None:
            msg = f"Must assign a Unit before saving Item {self}"
            raise ValueError(msg)
        if self.user is None:
            self.user = self.unit.user
        elif self.user_id != self.unit.user_id:
            msg = f"User for Unit {self.unit} and Item {self} must be the same"
            raise ValueError(msg)

        super().save(*args, **kwargs)

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

