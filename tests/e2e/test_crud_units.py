"""E2E tests for unit CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from core.models import Item, Unit

from .conftest import (
    DEFAULT_MAX_STEPS,
    LOCATION_HOUSE,
    LOCATION_OFFICE,
    NEW_UNIT_DESCRIPTION,
    NEW_UNIT_NAME,
    UNIT_DESK,
    UNIT_GARAGE,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Unit creation tests
# ---------------------------------------------------------------------------


async def test_create_unit(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
) -> None:
    """Verify that a user can create a standalone unit from the browse page."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click the '+ Unit' button in the header. "
            f"In the dialog, enter the name '{NEW_UNIT_NAME}' and leave "
            "the container as 'No container (standalone)'. "
            "Click 'Create' to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert await sync_to_async(Unit.objects.filter(name=NEW_UNIT_NAME).exists)()


async def test_create_unit_in_location(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify creating a unit assigned to a location container."""
    house = seeded_inventory["locations"][0]

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click the '+ Unit' button in the header. "
            f"In the dialog, enter the name '{NEW_UNIT_NAME}'. "
            f"Choose '{LOCATION_HOUSE}' from the Container dropdown. "
            "Click 'Create' to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    @sync_to_async
    def _check_unit() -> bool:
        return Unit.objects.filter(name=NEW_UNIT_NAME, location_id=house.id).exists()

    assert await _check_unit()


async def test_create_nested_unit(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify creating a unit nested inside a parent unit."""
    garage = seeded_inventory["units"][0]

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click the '+ Unit' button in the header. "
            f"In the dialog, enter the name '{NEW_UNIT_NAME}'. "
            f"Choose '{UNIT_GARAGE}' from the Container dropdown. "
            "Click 'Create' to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    @sync_to_async
    def _check_unit() -> bool:
        return Unit.objects.filter(
            name=NEW_UNIT_NAME,
            parent_unit_id=garage.id,
        ).exists()

    assert await _check_unit()


# ---------------------------------------------------------------------------
# Unit edit tests
# ---------------------------------------------------------------------------


async def test_edit_unit_name(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify editing a unit's name via the browse page edit dialog."""
    unit = seeded_inventory["units"][0]  # Garage Shelf

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}' to see its units. "
            f"Find the unit called '{UNIT_GARAGE}'. Open its menu "
            "(click the three-dot icon on the unit card) and click Edit. "
            "In the edit dialog, change the name to 'Garage Cabinet' "
            "and click 'Save'."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(unit.refresh_from_db)()
    assert unit.name == "Garage Cabinet"


async def test_edit_unit_description(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify editing a unit's description via the full edit page."""
    unit = seeded_inventory["units"][0]  # Garage Shelf

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}' "
            "to go to its detail page. Click the edit icon (pencil) in "
            "the unit header. On the edit form, enter the description "
            f"'{NEW_UNIT_DESCRIPTION}' and click 'Save Changes'."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(unit.refresh_from_db)()
    assert unit.description == NEW_UNIT_DESCRIPTION


async def test_edit_unit_dimensions(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify adding dimensions to a unit via the full edit page."""
    unit = seeded_inventory["units"][0]  # Garage Shelf

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}' "
            "to go to its detail page. Click the edit icon (pencil) in "
            "the unit header. On the edit form, scroll to the Dimensions "
            "section. Enter 24 for Length, 12 for Width, and 8 for Height. "
            "Select 'Inches' (in) as the unit of measurement. "
            "Click 'Save Changes'."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(unit.refresh_from_db)()
    assert unit.length == 24.0
    assert unit.width == 12.0
    assert unit.height == 8.0
    assert unit.dimensions_unit == "in"


# ---------------------------------------------------------------------------
# Unit delete tests
# ---------------------------------------------------------------------------


async def test_delete_unit(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify deleting a unit via the browse page delete dialog."""
    desk = seeded_inventory["units"][2]  # Desk Drawer (in Office)
    desk_id = desk.id

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_OFFICE}' to see its units. "
            f"Find the unit called '{UNIT_DESK}'. Open its menu "
            "(click the three-dot icon on the unit card) and click Delete. "
            "Confirm the deletion when prompted."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert not await sync_to_async(Unit.objects.filter(id=desk_id).exists)()


async def test_delete_unit_cascades_items(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify that deleting a unit also deletes its items."""
    garage = seeded_inventory["units"][0]  # Garage Shelf
    garage_id = garage.id
    # Garage Shelf contains Red Jacket and Screwdriver Set
    item_ids = [
        seeded_inventory["items"][0].id,
        seeded_inventory["items"][1].id,
    ]

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}' to see its units. "
            f"Find the unit called '{UNIT_GARAGE}'. Open its menu "
            "(click the three-dot icon on the unit card) and click Delete. "
            "Confirm the deletion when prompted."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert not await sync_to_async(Unit.objects.filter(id=garage_id).exists)()
    assert not await sync_to_async(
        Item.objects.filter(id__in=item_ids).exists,
    )()


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


async def test_duplicate_unit_name_rejected(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify that creating a unit with a duplicate name is rejected."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            "Click the '+ Unit' button in the header. "
            f"In the dialog, enter the name '{UNIT_GARAGE}' and "
            "click 'Create' to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    # Should still be exactly 1 unit named "Garage Shelf"
    count = await sync_to_async(Unit.objects.filter(name=UNIT_GARAGE).count)()
    assert count == 1
