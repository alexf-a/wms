from django.contrib.auth.models import User
from django.db import models
import qrcode
from django.core.files.base import ContentFile
from io import BytesIO

class WMSUser(User):
    """Custom user model extending Django's built-in User model."""

    class Meta:
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
        unique_together = ("user", "bin")

class Bin(models.Model):
    """Model representing a storage bin.

    Attributes:
        user (User): The primary owner of the bin.
        shared_users (ManyToManyField): Users with shared access to the bin.
        name (str): The name of the bin.
        description (str): A description of the bin.
        qr_code (ImageField): The QR code image for the bin.
        location (str): The location of the bin.
        length (float): The length of the bin.
        width (float): The width of the bin.
        height (float): The height of the bin.
    """
    user = models.ForeignKey(User, related_name="bins", on_delete=models.CASCADE)
    shared_users = models.ManyToManyField(
        User,
        through="BinSharedAccess",
        blank=True,
        related_name="shared_bins"
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    qr_code = models.ImageField(upload_to="qr_codes/")
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

class Item(models.Model):
    """Model representing an item stored in a bin.

    Attributes:
        name (str): The name of the item.
        description (str): A description of the item.
        created_on (DateTimeField): The date and time the item was created.
        image (ImageField): An optional image of the item.
        bin (Bin): The bin in which the item is stored.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="item_images/", blank=True, null=True)
    bin = models.ForeignKey(Bin, related_name="items", on_delete=models.CASCADE)

    def __str__(self):
        return self.name

