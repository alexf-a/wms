"""E2E tests for authentication flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .conftest import DEFAULT_DEFAULT_MAX_STEPS

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


async def test_login_success(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    test_user_credentials: dict[str, str],
) -> None:
    """Verify that a user can log in with valid credentials and reach the home page."""
    agent = agent_factory(
        task=(
            f"Go to {live_server.url}/login/ and log in with "
            f"email '{test_user_credentials['email']}' and "
            f"password '{test_user_credentials['password']}'. "
            "After logging in, you are done."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    final_url = result.history[-1].state.url
    # Successful login redirects to the home page (root URL)
    assert final_url.rstrip("/") == live_server.url


async def test_login_invalid_credentials(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    test_user_credentials: dict[str, str],
) -> None:
    """Verify that invalid credentials keep the user on the login page."""
    agent = agent_factory(
        task=(
            f"Go to {live_server.url}/login/ and try to log in with "
            f"email '{test_user_credentials['email']}' and "
            "password 'wrong-password-123'. "
            "After submitting the form, you are done."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    final_url = result.history[-1].state.url
    # Failed login stays on the login page
    assert "/login" in final_url
