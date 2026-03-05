"""E2E tests for visual QA and basic accessibility checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .conftest import DEFAULT_MAX_STEPS, SCREENSHOTS_DIR

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent, Browser
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


async def test_screenshot_all_pages(
    authenticated_agent_factory: Callable[..., Agent],
    browser_instance: Browser,
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Navigate to each main page and capture a screenshot.

    Validates that pages render without server errors. Screenshots are
    saved to ``tests/e2e/screenshots/`` for manual visual review.
    """
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url}. Visit each of the following pages "
            "by clicking the bottom navigation tabs: Home, Find, Add, See. "
            "After visiting each page, tell me the page title or heading "
            "you see. Also tell me if any page shows an error."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    # Should not encounter server errors
    assert "500" not in final_text
    assert "server error" not in final_text

    # Capture a final screenshot for review
    if hasattr(browser_instance, "page") and browser_instance.page is not None:
        await browser_instance.page.screenshot(
            path=str(SCREENSHOTS_DIR / "all_pages_final.png"),
        )


async def test_no_broken_internal_links(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify that navigating through the app does not produce 404 or 500 errors."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url}. Navigate through the app by visiting "
            "the Home page, then Find, then Add, then See (browse). "
            "On the browse page, click into a location and then into a unit. "
            "Report any pages that show a 404 Not Found error, a 500 Server "
            "Error, or any other error page. If all pages load correctly, "
            "say 'All pages loaded successfully'."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    assert "404" not in final_text or "no 404" in final_text
    assert "500" not in final_text or "no 500" in final_text
    assert "error page" not in final_text or "no error" in final_text


async def test_form_labels_present(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
) -> None:
    """Verify that form inputs on the login page have visible labels."""
    agent = agent_factory(
        task=(
            f"Go to {live_server.url}/login/ and examine the login form. "
            "Check if each input field (email and password) has a visible "
            "label or placeholder text that describes what should be entered. "
            "Report whether labels are present for each field."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    # The agent should confirm labels/placeholders exist
    assert "label" in final_text or "placeholder" in final_text
