"""Tests for core/forms.py to verify form validation and behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from core.forms import PasswordChangeForm

if TYPE_CHECKING:
    from core.models import WMSUser as User


@pytest.mark.django_db
class TestPasswordChangeForm:
    """Tests for PasswordChangeForm validation and password change logic."""

    def test_form_requires_user_parameter(self):
        """Test form requires user parameter for initialization."""
        with pytest.raises(TypeError):
            PasswordChangeForm()

    def test_clean_current_password_accepts_correct_password(self, user: User):
        """Test current password validation passes with correct password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

    def test_clean_current_password_rejects_incorrect_password(self, user: User):
        """Test current password validation fails with incorrect password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "wrongpassword",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert not form.is_valid()
        assert "current_password" in form.errors

    def test_clean_new_password1_rejects_too_short(self, user: User):
        """Test new password validation rejects passwords that are too short."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "short",  # Less than 8 characters
                "new_password2": "short",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_all_numeric(self, user: User):
        """Test new password validation rejects all-numeric passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "12345678",  # All numeric
                "new_password2": "12345678",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_common_password(self, user: User):
        """Test new password validation rejects common passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "password123",  # Common password
                "new_password2": "password123",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_new_password1_rejects_similar_to_email(self, user: User):
        """Test new password validation rejects passwords similar to user email."""
        # User email is "owner@example.com"
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "owner@example.com",  # Too similar to email
                "new_password2": "owner@example.com",
            }
        )
        assert not form.is_valid()
        assert "new_password1" in form.errors

    def test_clean_accepts_strong_password(self, user: User):
        """Test new password validation accepts strong passwords."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "StrongPassword123!",
                "new_password2": "StrongPassword123!",
            }
        )
        assert form.is_valid()

    def test_clean_rejects_mismatched_passwords(self, user: User):
        """Test cross-field validation rejects when passwords don't match."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "DifferentPassword123!",
            }
        )
        assert not form.is_valid()
        assert "__all__" in form.errors or "new_password2" in form.errors

    def test_clean_accepts_matching_passwords(self, user: User):
        """Test cross-field validation passes when passwords match."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

    def test_save_updates_user_password(self, user: User):
        """Test save method updates the user's password."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

        saved_user = form.save()

        assert saved_user == user
        assert user.check_password("NewSecurePass123!")
        assert not user.check_password("testpass123")

    def test_save_without_commit_does_not_persist(self, user: User):
        """Test save with commit=False doesn't persist to database."""
        form = PasswordChangeForm(
            user,
            data={
                "current_password": "testpass123",
                "new_password1": "NewSecurePass123!",
                "new_password2": "NewSecurePass123!",
            }
        )
        assert form.is_valid()

        saved_user = form.save(commit=False)

        # Password is set in memory but not saved
        assert saved_user.check_password("NewSecurePass123!")

        # Refresh from DB - should still have old password
        user.refresh_from_db()
        assert user.check_password("testpass123")
