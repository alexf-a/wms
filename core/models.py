import base64
from urllib.parse import urljoin

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from schemas import ItemSearchInput

from .upload_paths import user_item_image_upload_path
from .utils import generate_bin_access_token, get_qr_code_file


class WMSUser(User):
    """Custom user model extending Django's built-in User model."""

    class Meta:
        """Metadata for the WMSUser proxy."""

        app_label = "core"

class BinSharedAccess(models.Model):
    """Model to handle shared access to bins with specific permissions.

    Attributes:
        user (User): The user with shared access.
        bin (Bin): The bin to which access is shared.
        permission (str): The level of permission (e.g., "read", "write").
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bin = models.ForeignKey("Bin", on_delete=models.CASCADE)
    permission = models.CharField(max_length=50, default="read")

    class Meta:
        """Model constraints for shared bin access."""

        unique_together = ("user", "bin")

    def __str__(self) -> str:
        return f"{self.user.username} → {self.bin.name} ({self.permission})"

class Bin(models.Model):
    """Model representing a storage bin.

    Attributes:
        user (User): The primary owner of the bin.
        shared_users (ManyToManyField): Users with shared access to the bin.
        name (str): The name of the bin.
        description (str): A description of the bin.
        location (str): The location of the bin.
        length (float): The length of the bin in inches.
        width (float): The width of the bin in inches.
        height (float): The height of the bin in inches.
    """
    user = models.ForeignKey(User, related_name="bins", on_delete=models.CASCADE)
    shared_users = models.ManyToManyField(
        User,
        through="BinSharedAccess",
        blank=True,
        related_name="shared_bins"
    )
    name = models.CharField(max_length=1000)
    description = models.TextField(max_length=5000)
    access_token = models.CharField(max_length=48, unique=True, default=generate_bin_access_token)
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True, help_text="in inches")
    width = models.FloatField(blank=True, null=True, help_text="in inches")
    height = models.FloatField(blank=True, null=True, help_text="in inches")

    class Meta:
        """Model constraints for the Bin model."""

        unique_together = ("user", "name")

    def __str__(self) -> str:
        return self.name

    def get_qr_filename(self) -> str:
        """Return a deterministic filename for the bin's QR code image."""
        return f"{slugify(self.name) or 'bin'}_qr.png"

    def get_detail_path(self) -> str:
        """Return the relative URL path to this bin's detail view."""
        return reverse(
            "bin_detail",
            kwargs={"user_id": self.user_id, "access_token": self.access_token},
        )

    def get_qr_code(self, *, base_url: str) -> ContentFile:
        """Generate a QR code file pointing to this bin's detail view.

        Args:
            base_url: The absolute base URL of the site (e.g., "https://app.example.com/").

        Returns:
            ContentFile: An in-memory QR code image for the bin.
        """
        normalized_base = base_url.rstrip("/") + "/"
        detail_url = urljoin(normalized_base, self.get_detail_path().lstrip("/"))
        return get_qr_code_file(detail_url, filename=self.get_qr_filename())

class Item(models.Model):
    """Model representing an item stored in a bin.

    Attributes:
        name (str): The name of the item.
        description (str): A description of the item.
        created_on (DateTimeField): The date and time the item was created.
        image (ImageField): An optional image of the item.
        bin (Bin): The bin in which the item is stored.
    """
    user = models.ForeignKey(User, related_name="items", on_delete=models.CASCADE, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=user_item_image_upload_path, blank=True, null=True)
    bin = models.ForeignKey(Bin, related_name="items", on_delete=models.CASCADE)

    class Meta:
        """Model constraints for Item."""

        unique_together = ("user", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the item after verifying ownership alignment."""
        if self.bin is None:
            msg = f"Must assign a Bin before saving Item {self}"
            raise ValueError(msg)
        if self.user is None:
            self.user = self.bin.user
        elif self.user_id != self.bin.user_id:
            msg = f"User for Bin {self.bin} and Item {self} must be the same"
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
            bin_name=self.bin.name,
            image=image
        )

