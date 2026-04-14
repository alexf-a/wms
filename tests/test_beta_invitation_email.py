"""Tests for beta invitation email functionality."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.test import override_settings

from core.email import send_beta_invitation_email
from core.models import WMSUser

EMAIL_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "test@mystuff.tools",
    "APP_URL": "https://mystuff.tools",
}


class TestSendBetaInvitationEmail:

    @override_settings(**EMAIL_SETTINGS)
    def test_sends_email_successfully(self):
        result = send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        assert result is True
        assert len(mail.outbox) == 1

        msg = mail.outbox[0]
        assert msg.subject == "You're invited to WMS"
        assert msg.to == ["beta@example.com"]
        assert msg.from_email == "test@mystuff.tools"

    @override_settings(**EMAIL_SETTINGS)
    def test_email_contains_credentials_in_text_body(self):
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        msg = mail.outbox[0]
        assert "beta@example.com" in msg.body
        assert "TestPass123!" in msg.body

    @override_settings(**EMAIL_SETTINGS)
    def test_email_contains_credentials_in_html_body(self):
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        msg = mail.outbox[0]
        html_body = msg.alternatives[0][0]
        assert "beta@example.com" in html_body
        assert "TestPass123!" in html_body

    @override_settings(**EMAIL_SETTINGS)
    def test_email_contains_app_urls(self):
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        msg = mail.outbox[0]
        assert "https://mystuff.tools/login/" in msg.body
        assert "https://mystuff.tools/getting-started/" in msg.body

        html_body = msg.alternatives[0][0]
        assert "https://mystuff.tools/login/" in html_body
        assert "https://mystuff.tools/getting-started/" in html_body

    @override_settings(**EMAIL_SETTINGS)
    def test_html_alternative_is_attached(self):
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        msg = mail.outbox[0]
        assert len(msg.alternatives) == 1
        assert msg.alternatives[0][1] == "text/html"

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@mystuff.tools",
        APP_URL="https://custom.example.com",
    )
    def test_uses_app_url_from_settings(self):
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        msg = mail.outbox[0]
        assert "https://custom.example.com/login/" in msg.body
        assert "https://custom.example.com/getting-started/" in msg.body

    @override_settings(**EMAIL_SETTINGS)
    @patch("core.email.EmailMultiAlternatives.send", side_effect=Exception("SES error"))
    def test_returns_false_on_send_failure(self, mock_send):
        result = send_beta_invitation_email(email="beta@example.com", password="TestPass123!")

        assert result is False

    @override_settings(**EMAIL_SETTINGS)
    @patch("core.email.EmailMultiAlternatives.send", side_effect=Exception("SES error"))
    def test_does_not_propagate_exception(self, mock_send):
        # Should not raise
        send_beta_invitation_email(email="beta@example.com", password="TestPass123!")


@pytest.mark.django_db
class TestCreateBetaUsersEmailIntegration:

    @override_settings(**EMAIL_SETTINGS)
    @patch.dict("os.environ", {
        "BETA_USER_EMAILS": "new1@example.com,new2@example.com",
        "BETA_USER_DEFAULT_PASSWORD": "BetaPass123!",
    })
    def test_sends_email_for_new_users(self):
        from django.core.management import call_command

        call_command("create_beta_users", stdout=StringIO())

        assert len(mail.outbox) == 2
        recipients = {msg.to[0] for msg in mail.outbox}
        assert recipients == {"new1@example.com", "new2@example.com"}

    @override_settings(**EMAIL_SETTINGS)
    @patch.dict("os.environ", {
        "BETA_USER_EMAILS": "existing@example.com",
        "BETA_USER_DEFAULT_PASSWORD": "BetaPass123!",
    })
    def test_skips_email_for_existing_users(self):
        from django.core.management import call_command

        WMSUser.objects.create_user(email="existing@example.com", password="oldpass")

        call_command("create_beta_users", stdout=StringIO())

        assert len(mail.outbox) == 0

    @override_settings(**EMAIL_SETTINGS)
    @patch("core.email.EmailMultiAlternatives.send", side_effect=Exception("SES error"))
    @patch.dict("os.environ", {
        "BETA_USER_EMAILS": "failmail@example.com",
        "BETA_USER_DEFAULT_PASSWORD": "BetaPass123!",
    })
    def test_creates_user_even_if_email_fails(self, mock_send):
        from django.core.management import call_command

        call_command("create_beta_users", stdout=StringIO())

        assert WMSUser.objects.filter(email="failmail@example.com").exists()
        user = WMSUser.objects.get(email="failmail@example.com")
        assert user.must_change_password is True

    @override_settings(**EMAIL_SETTINGS)
    @patch.dict("os.environ", {
        "BETA_USER_EMAILS": "mixed@example.com,existing@example.com",
        "BETA_USER_DEFAULT_PASSWORD": "BetaPass123!",
    })
    def test_only_emails_new_users_in_mixed_list(self):
        from django.core.management import call_command

        WMSUser.objects.create_user(email="existing@example.com", password="oldpass")

        call_command("create_beta_users", stdout=StringIO())

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["mixed@example.com"]
