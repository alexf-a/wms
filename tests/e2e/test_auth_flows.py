"""E2E tests for authentication flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

MAX_STEPS = 20


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
            "After logging in, confirm that you are on the home page. "
            "Tell me what page you ended up on."
        ),
    )
    result = await agent.run(max_steps=MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    # The agent should report being on the home/dashboard page, not still on login
    assert "login" not in final_text or "logged in" in final_text or "home" in final_text


async def test_login_invalid_credentials(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    test_user_credentials: dict[str, str],
) -> None:
    """Verify that invalid credentials show an error message."""
    agent = agent_factory(
        task=(
            f"Go to {live_server.url}/login/ and try to log in with "
            f"email '{test_user_credentials['email']}' and "
            "password 'wrong-password-123'. "
            "Tell me what happens. Is there an error message?"
        ),
    )
    result = await agent.run(max_steps=MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    assert "error" in final_text or "incorrect" in final_text or "invalid" in final_text or "wrong" in final_text
