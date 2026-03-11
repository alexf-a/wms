"""E2E tests for item search functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .conftest import (
    DEFAULT_MAX_STEPS,
    ITEM_RED_JACKET,
    LOCATION_HOUSE,
    UNIT_GARAGE,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent, Browser
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Search result display
# ---------------------------------------------------------------------------


async def test_search_finds_existing_item(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    browser_instance: Browser,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify that searching for an existing item displays a result card."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Find' in the bottom "
            f"navigation. In the search input, type '{ITEM_RED_JACKET}' "
            "and submit the search (press Enter or click the arrow button)."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    page = browser_instance.page
    result_section = await page.query_selector("section[aria-live='polite']")
    assert result_section is not None, "Search results section not found on page"


async def test_search_result_shows_name_and_breadcrumb(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    browser_instance: Browser,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify result card displays item name, placeholder image, and location breadcrumb."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Find' in the bottom "
            f"navigation. In the search input, type '{ITEM_RED_JACKET}' "
            "and submit the search."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    page = browser_instance.page
    result_card = await page.query_selector("section[aria-live='polite'] a")
    assert result_card is not None, "Result card link not found"

    card_text = await result_card.inner_text()
    assert ITEM_RED_JACKET in card_text, f"Item name not in card: {card_text}"

    breadcrumb = f"{LOCATION_HOUSE} > {UNIT_GARAGE}"
    assert breadcrumb in card_text, f"Breadcrumb '{breadcrumb}' not in card: {card_text}"

    # Seeded items have no image — verify placeholder SVG is rendered
    placeholder = await result_card.query_selector("svg")
    assert placeholder is not None, "Placeholder image icon not found in result card"


# ---------------------------------------------------------------------------
# No results
# ---------------------------------------------------------------------------


async def test_search_no_results_for_nonexistent_item(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    browser_instance: Browser,
    # No seeded_inventory — DB has user but zero items.
    # The mock returns ITEM_RED_JACKET, but the view's DB check finds nothing.
) -> None:
    """Verify that searching when no items exist shows 'No items found'."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Find' in the bottom "
            f"navigation. In the search input, type '{ITEM_RED_JACKET}' "
            "and submit the search."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    page = browser_instance.page
    body_text = await page.inner_text("body")
    assert "No items found" in body_text


# ---------------------------------------------------------------------------
# Result card navigation
# ---------------------------------------------------------------------------


async def test_search_result_links_to_unit(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that clicking the result card navigates to the unit detail page."""
    garage = seeded_inventory["units"][0]  # Garage Shelf

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Find' in the bottom "
            f"navigation. In the search input, type '{ITEM_RED_JACKET}' "
            "and submit the search. After the result card appears, "
            "click on the result card to navigate to the unit page."
        ),
    )
    result = await agent.run(max_steps=DEFAULT_MAX_STEPS)

    final_url = result.history[-1].state.url
    assert str(garage.access_token) in final_url
