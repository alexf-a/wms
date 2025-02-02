from django.contrib.auth.models import User
from django.db import models
import qrcode
from django.core.files.base import ContentFile
from io import BytesIO

class WMSUser(User):
    class Meta:
        app_label = 'core'
# Create your models here.

class Bin(models.Model):
    name = models.CharField(max_length=255, unique=True)  # Make name unique
    description = models.TextField()
    qr_code = models.ImageField(upload_to='qr_codes/')
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.qr_code:
            qr = qrcode.make(self.name)
            buffer = BytesIO()
            qr.save(buffer, format='PNG')
            file_name = f'{self.name}_qr.png'
            self.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
