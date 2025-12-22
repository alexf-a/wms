"""Custom authentication backends for WMS."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailBackend(ModelBackend):
    """Authentication backend that allows users to log in with their email address."""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate user by email.
        
        Args:
            request: The HTTP request object.
            username: Django's auth forms pass the login field as 'username',
                but for WMS this contains the user's email address.
            password: The user's password.
            **kwargs: Additional keyword arguments (may contain 'email').
        
        Returns:
            User object if authentication succeeds, None otherwise.
        """
        UserModel = get_user_model()
        
        # Get email from either 'username' param (Django's default form field name)
        # or 'email' param if called directly
        email = username or kwargs.get('email')
        
        if email is None or password is None:
            return None
        
        try:
            # Look up user by email (case-insensitive)
            user = UserModel.objects.get(Q(email__iexact=email))
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user.
            UserModel().set_password(password)
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
