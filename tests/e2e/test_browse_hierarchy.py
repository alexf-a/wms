"""E2E tests for browsing the location/unit/item hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

MAX_STEPS = 25


async def test_browse_locations_list(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify that the browse page lists all locations with their unit counts."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "List all the locations you see and how many units each has."
        ),
    )
    result = await agent.run(max_steps=MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    # Should see both seeded locations
    assert "my house" in final_text
    assert "office" in final_text


async def test_browse_drill_down(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify drilling down: location -> unit -> items."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click on 'My House', then click on 'Garage Shelf'. "
            "List all items you see inside that unit."
        ),
    )
    result = await agent.run(max_steps=MAX_STEPS)
    final_text = result.final_result().lower() if result.final_result() else ""
    # Should see items in the Garage Shelf unit
    assert "red jacket" in final_text or "screwdriver" in final_text
