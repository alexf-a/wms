"""Context processors for WMS templates.

Provides additional context variables to all templates.
"""
from django.conf import settings


def registration_settings(request):
    """Add REGISTRATION_ENABLED setting to template context.
    
    Args:
        request: The HTTP request object.
    
    Returns:
        Dictionary with REGISTRATION_ENABLED setting.
    """
    return {
        'REGISTRATION_ENABLED': settings.REGISTRATION_ENABLED,
    }
