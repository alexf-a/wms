from django.contrib.auth.models import User
from django.db import models
import qrcode
from django.core.files.base import ContentFile
from io import BytesIO

class WMSUser(User):
    class Meta:
        app_label = 'core'
# Create your models here.

class BinSharedAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bin = models.ForeignKey('Bin', on_delete=models.CASCADE)
    # Placeholder for permission levels (e.g., "read", "write", etc.)
    permission = models.CharField(max_length=50, default='read')
    # ...existing code or timestamps if needed...

    class Meta:
        unique_together = ('user', 'bin')

class Bin(models.Model):
    user = models.ForeignKey(User, related_name='bins', on_delete=models.CASCADE)  # Primary owner
    shared_users = models.ManyToManyField(
        User,
        through='BinSharedAccess',
        blank=True,
        related_name='shared_bins'
    )  # Allow shared access with permissions
    name = models.CharField(max_length=255, unique=True)  # Make name unique
    description = models.TextField()
    qr_code = models.ImageField(upload_to='qr_codes/')
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='item_images/', blank=True, null=True)
    bin = models.ForeignKey(Bin, related_name='items', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

