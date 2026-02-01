"""Tests for core/middleware.py to verify middleware behavior."""

from __future__ import annotations

import http
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.middleware import MustChangePasswordMiddleware

User = get_user_model()


@pytest.mark.django_db
class TestMustChangePasswordMiddleware:
    """Tests for MustChangePasswordMiddleware password change enforcement."""

    def test_allows_unauthenticated_users(self, client):
        """Test middleware allows unauthenticated users to access pages."""
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK

    def test_allows_users_without_must_change_flag(self, client, user):
        """Test middleware allows normal users to access pages."""
        client.force_login(user)
        response = client.get(reverse("home_view"))
        assert response.status_code == http.HTTPStatus.OK

    def test_redirects_to_change_password_when_flag_set(self, client, user_must_change_password):
        """Test middleware redirects to change_password when must_change_password is True."""
        client.force_login(user_must_change_password)
        response = client.get(reverse("home_view"))
        
        assert response.status_code == http.HTTPStatus.FOUND
        assert response.url == reverse("change_password")

    def test_allows_access_to_change_password_view(self, client, user_must_change_password):
        """Test middleware allows access to change_password view itself."""
        client.force_login(user_must_change_password)
        response = client.get(reverse("change_password"))
        
        # Should render the page, not redirect
        assert response.status_code == http.HTTPStatus.OK

    def test_allows_access_to_logout(self, client, user_must_change_password):
        """Test middleware allows access to logout URL."""
        client.force_login(user_must_change_password)
        response = client.get("/logout/")
        
        # Should process logout, not redirect to change_password
        assert response.status_code in [http.HTTPStatus.OK, http.HTTPStatus.FOUND]
        if response.status_code == http.HTTPStatus.FOUND:
            assert response.url != reverse("change_password")

    def test_allows_access_to_static_files(self, client, user_must_change_password):
        """Test middleware allows access to static files."""
        client.force_login(user_must_change_password)
        # Static files would normally return 404 if not found, but shouldn't redirect
        response = client.get("/static/core/css/test.css")
        
        # Should get 404 or 200, not redirect to change_password
        assert response.status_code in [http.HTTPStatus.NOT_FOUND, http.HTTPStatus.OK]

    def test_allows_access_to_media_files(self, client, user_must_change_password):
        """Test middleware allows access to media files."""
        client.force_login(user_must_change_password)
        # Media files would normally return 404 if not found, but shouldn't redirect
        response = client.get("/media/item_images/test.jpg")
        
        # Should get 404 or 200, not redirect to change_password
        assert response.status_code in [http.HTTPStatus.NOT_FOUND, http.HTTPStatus.OK]

    def test_redirects_multiple_different_urls(self, client, user_must_change_password):
        """Test middleware redirects multiple different URLs to change_password."""
        client.force_login(user_must_change_password)
        
        urls_to_test = [
            reverse("home_view"),
            reverse("list_units"),
            reverse("account"),
        ]
        
        for url in urls_to_test:
            response = client.get(url)
            assert response.status_code == http.HTTPStatus.FOUND
            assert response.url == reverse("change_password")
