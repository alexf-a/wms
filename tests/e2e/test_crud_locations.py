"""E2E tests for location CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from core.models import Location

from .conftest import DEFAULT_MAX_STEPS, LOCATION_OFFICE

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


async def test_create_location(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
) -> None:
    """Verify that a user can create a new location from the browse page."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Create a new location by clicking the add/create button. "
            "Name it 'Test Garage' and submit the form. "
            "Confirm that 'Test Garage' now appears in the locations list."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    # Verify in database
    assert await sync_to_async(Location.objects.filter(name="Test Garage").exists)()


async def test_edit_location(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that a user can edit an existing location's name."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Find the location called '{LOCATION_OFFICE}'. Open its menu (look for "
            "a three-dot or edit icon) and edit it. Change the name to "
            "'Main Office' and save. Confirm the updated name is shown."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    office = seeded_inventory["locations"][1]
    await sync_to_async(office.refresh_from_db)()
    assert office.name == "Main Office"


async def test_delete_location(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that a user can delete a location."""
    office = seeded_inventory["locations"][1]
    office_id = office.id
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Find the location called '{LOCATION_OFFICE}'. Open its menu and delete it. "
            "Confirm the deletion when prompted. "
            f"Confirm that '{LOCATION_OFFICE}' is no longer in the list."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert not await sync_to_async(Location.objects.filter(id=office_id).exists)()
