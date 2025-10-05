from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


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
            return HttpResponse("ok")
        return self.get_response(request)
