from django.contrib.auth.models import User
from django.db import models

class WMSUser(User):
    class Meta:
        app_label = 'core'
# Create your models here.

class Bin(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    qr_code = models.ImageField(upload_to='qr_codes/')
    location = models.CharField(max_length=255, blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name
