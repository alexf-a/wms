"""E2E tests for item CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from core.models import Item

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

MAX_STEPS = 25


async def test_edit_item(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that a user can edit an item's name from the unit detail page."""
    item = seeded_inventory["items"][0]  # Red Jacket

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click on 'My House', then click on 'Garage Shelf'. "
            "Find the item called 'Red Jacket' and click on it to open "
            "its detail view. Edit its name to 'Blue Jacket' and save. "
            "Confirm the name has been updated."
        ),
    )
    await agent.run(max_steps=MAX_STEPS)
    item.refresh_from_db()
    assert item.name == "Blue Jacket"


async def test_delete_item(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that a user can delete an item from the unit detail page."""
    item = seeded_inventory["items"][0]  # Red Jacket
    item_id = item.id

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click on 'My House', then click on 'Garage Shelf'. "
            "Find the item called 'Red Jacket' and click on it. "
            "Delete the item and confirm the deletion when prompted. "
            "Confirm it is no longer shown in the list."
        ),
    )
    await agent.run(max_steps=MAX_STEPS)
    assert not Item.objects.filter(id=item_id).exists()
