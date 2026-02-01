from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class HealthCheckMiddleware:
    """Middleware to handle health checks without ALLOWED_HOSTS validation.

    This middleware intercepts requests to the configured health check endpoint
    and returns a simple "ok" response without going through Django's normal
    request processing, which includes ALLOWED_HOSTS validation.

    The health check path can be configured via the HEALTH_CHECK_PATH setting.
    Defaults to "/healthz/" if not specified.

    This is safe for health checks since they don't need to access any
    application logic or user data.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware with the next middleware in the chain."""
        self.get_response = get_response
        # Get the health check path from settings - must be explicitly configured
        try:
            self.health_check_path = settings.HEALTH_CHECK_PATH
        except AttributeError as exc:
            msg = (
                "HEALTH_CHECK_PATH setting is required when using HealthCheckMiddleware. "
                "Please add HEALTH_CHECK_PATH = '/healthz/' to your Django settings."
            )
            raise AttributeError(msg) from exc

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and return either health check or normal response."""
        if request.path == self.health_check_path:
            return JsonResponse({"status": "ok"})
        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """Middleware to force users to change their password if must_change_password is True.
    
    Beta users created with a default password will have must_change_password=True.
    They will be redirected to the change password page on every request until
    they change their password.
    
    Whitelisted URLs (allowed without password change):
    - change_password: The password change form itself
    - logout: Allow users to logout
    - health_check: The health check endpoint
    - Static/media files: Allow loading CSS/JS/images
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware with the next middleware in the chain."""
        self.get_response = get_response
        # Get the health check path from settings
        self.health_check_path = getattr(settings, "HEALTH_CHECK_PATH", "/healthz/")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and redirect to password change if required."""
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip if user doesn't need to change password
        if not getattr(request.user, "must_change_password", False):
            return self.get_response(request)

        # Whitelist URLs that don't require password change
        change_password_url = reverse("change_password")
        logout_url = reverse("logout")

        # Allow access to change_password, logout, health_check, and static/media files
        if (
            request.path
            in (change_password_url, logout_url, self.health_check_path)
            or request.path.startswith("/static/")
            or request.path.startswith("/media/")
        ):
            return self.get_response(request)

        # Redirect to password change page
        return redirect("change_password")
