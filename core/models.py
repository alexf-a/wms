from django.contrib.auth.models import User

class WMSUser(User):
    class Meta:
        app_label = 'core'
# Create your models here.
