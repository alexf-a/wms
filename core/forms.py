from django.contrib.auth.forms import UserCreationForm
from .models import WMSUser

class WMSUserCreationForm(UserCreationForm):
    class Meta:
        model = WMSUser
        fields = ('username', 'password1', 'password2')