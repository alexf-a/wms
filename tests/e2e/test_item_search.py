"""E2E tests for item search functionality.

Uses real LLM calls (``@pytest.mark.real_llm``) against a small 5-item
corpus so the full search pipeline is exercised end-to-end.  Searches use
exact item names to avoid testing LLM search quality — the goal is to
verify the pipeline, not the model's ranking ability.  With an exact name
and a small corpus, the candidate search (Haiku) finds a single
high-confidence match and skips the expensive Sonnet follow-up.
"""

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

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.django_db(transaction=True),
    pytest.mark.real_llm,
]


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

    page = await browser_instance.get_current_page()
    has_results = await page.evaluate(
        "() => String(document.querySelector(\"section[aria-live='polite']\") !== null)",
    )
    assert has_results == "true", "Search results section not found on page"


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

    page = await browser_instance.get_current_page()

    card_text = await page.evaluate(
        "() => document.querySelector(\"section[aria-live='polite'] a\")?.innerText || ''",
    )
    assert ITEM_RED_JACKET in card_text, f"Item name not in card: {card_text}"

    breadcrumb = f"{LOCATION_HOUSE} > {UNIT_GARAGE}"
    assert breadcrumb in card_text, f"Breadcrumb '{breadcrumb}' not in card: {card_text}"

    # Seeded items have no image — verify placeholder SVG is rendered
    has_placeholder = await page.evaluate(
        "() => String(document.querySelector(\"section[aria-live='polite'] a svg\") !== null)",
    )
    assert has_placeholder == "true", "Placeholder image icon not found in result card"


# ---------------------------------------------------------------------------
# No results
# ---------------------------------------------------------------------------


async def test_search_no_results_for_nonexistent_item(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    browser_instance: Browser,
    # No seeded_inventory — DB has user but zero items.
    # The LLM receives an empty corpus and may return a hallucinated name,
    # but the view's DB verification (Item.objects.filter) finds nothing,
    # so the template renders the "No items found" empty state regardless.
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

    page = await browser_instance.get_current_page()
    body_text = await page.evaluate("() => document.body.innerText")
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
