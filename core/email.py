"""Email utilities for the WMS application.

Provides functions for sending branded HTML emails to users.
"""

import logging
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_beta_invitation_email(*, email: str, password: str) -> bool:
    """Send a branded HTML beta invitation email to a new user.

    Args:
        email: The recipient email address.
        password: The default password assigned to the user.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    app_url = getattr(settings, "APP_URL", "https://mystuff.tools")
    login_url = urljoin(app_url, "/login/")
    getting_started_url = urljoin(app_url, "/getting-started/")

    context: dict[str, Any] = {
        "email": email,
        "password": password,
        "app_url": app_url,
        "login_url": login_url,
        "getting_started_url": getting_started_url,
    }

    subject = "You're invited to WMS"
    text_body = render_to_string("core/email/beta_invitation.txt", context)
    html_body = render_to_string("core/email/beta_invitation.html", context)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
    except Exception:
        logger.exception("Failed to send beta invitation email to %s", email)
        return False
    else:
        return True
