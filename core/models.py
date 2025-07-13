from django.contrib.auth.models import User
from django.db import models
import qrcode
from django.core.files.base import ContentFile
from io import BytesIO
import base64
from pathlib import Path
from schemas.item_search_input import ItemSearchInput

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
    name = models.CharField(max_length=1000)
    description = models.TextField(max_length=5000)
    qr_code = models.ImageField(upload_to="qr_codes/")
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name

    def to_search_prompt(self) -> str:
        """Format this Bin and its items as a string for LLM search context using ItemSearchInput.to_prompt."""
        item_qs = self.items.all()
        prompt = f"Bin: {self.name} (located at: {self.location or 'Unknown location'})\n"
        if item_qs.exists():
            prompt += "Contains items:\n" + str([item.to_search_input().to_prompt() for item in item_qs])
        else:
            prompt += "Contains no items\n"
        return prompt + "\n\n\n"

class Item(models.Model):
    """Model representing an item stored in a bin.

    Attributes:
        name (str): The name of the item.
        description (str): A description of the item.
        created_on (DateTimeField): The date and time the item was created.
        image (ImageField): An optional image of the item.
        bin (Bin): The bin in which the item is stored.
    """
    #TODO: Decide on PK. I am thinking it should be "name"
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="item_images/", blank=True, null=True)
    bin = models.ForeignKey(Bin, related_name="items", on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def to_search_input(self) -> ItemSearchInput:
        """Convert this Item instance to an ItemSearchInput for LLM search.
        
        Returns:
            ItemSearchInput: A Pydantic model with item data ready for LLM search
        """
        image = None
        
        # If item has an image, encode it to base64
        if self.image:
            try:
                image_path = Path(self.image.path)
                with image_path.open("rb") as image_file:
                    image_data = image_file.read()
                    image = base64.b64encode(image_data).decode("utf-8")
            except (FileNotFoundError, AttributeError):
                # If image file doesn't exist or can't be read, skip it
                pass
        
        return ItemSearchInput(
            name=self.name,
            description=self.description,
            bin_name=self.bin.name,
            image=image
        )

