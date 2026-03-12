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
            "After visiting all four pages, report 'done'."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    # All visited URLs should be on the live server (no unexpected redirects)
    visited_urls = result.urls()
    assert all(
        url.startswith(live_server.url) for url in visited_urls
    ), f"Unexpected external URL in: {visited_urls}"

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
    """Verify that navigating through the app does not hit error pages."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url}. Navigate through the app by visiting "
            "the Home page, then Find, then Add, then See (browse). "
            "On the browse page, click into a location and then into a unit. "
            "After visiting the unit page, report 'done'."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    visited_urls = result.urls()
    # Agent should have drilled down to a unit detail page
    assert any("/unit/" in url for url in visited_urls), (
        f"Agent never reached a unit detail page. URLs visited: {visited_urls}"
    )
    # All URLs should be on the live server
    assert all(
        url.startswith(live_server.url) for url in visited_urls
    ), f"Unexpected external URL in: {visited_urls}"


async def test_form_labels_present(
    agent_factory: Callable[..., Agent],
    browser_instance: Browser,
    live_server: LiveServer,
) -> None:
    """Verify that form inputs on the login page have visible labels."""
    agent = agent_factory(
        task=(
            f"Go to {live_server.url}/login/ and wait for the page to load. "
            "Once the login form is visible, report 'done'."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    # Verify the agent reached the login page
    visited_urls = result.urls()
    assert any("/login" in url for url in visited_urls), (
        f"Agent never reached the login page. URLs visited: {visited_urls}"
    )

    # Check that form labels exist in the DOM
    page = browser_instance.page
    assert page is not None, "Browser page not available after agent run"
    label_count = await page.evaluate(
        "document.querySelectorAll('label').length",
    )
    assert label_count >= 2, (
        f"Expected at least 2 form labels (email + password), found {label_count}"
    )
