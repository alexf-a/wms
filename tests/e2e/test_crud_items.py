"""E2E tests for item CRUD operations."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from core.models import Item

from .conftest import (
    DEFAULT_MAX_STEPS,
    ITEM_HEADPHONES,
    ITEM_RED_JACKET,
    ITEM_SCREWDRIVER,
    LOCATION_HOUSE,
    LOCATION_OFFICE,
    NEW_ITEM_AI,
    NEW_ITEM_MANUAL,
    NEW_ITEM_MANUAL_DESC,
    TEST_IMAGE_PATH,
    UNIT_CLOSET,
    UNIT_DESK,
    UNIT_GARAGE,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Existing tests — edit and delete from unit detail page
# ---------------------------------------------------------------------------


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
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Find the item called '{ITEM_RED_JACKET}' and click on it to open "
            "its detail view. Edit its name to 'Blue Jacket' and save. "
            "Confirm the name has been updated."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
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
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Find the item called '{ITEM_RED_JACKET}' and click on it. "
            "Delete the item and confirm the deletion when prompted. "
            "Confirm it is no longer shown in the list."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert not await sync_to_async(Item.objects.filter(id=item_id).exists)()


# ---------------------------------------------------------------------------
# Quantity stepper tests
# ---------------------------------------------------------------------------


async def test_increment_item_quantity(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory_with_quantities: dict,
) -> None:
    """Verify that clicking + on a quantity stepper increments the value."""
    item = seeded_inventory_with_quantities["items"][0]  # Red Jacket, qty=5

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Find the item '{ITEM_RED_JACKET}' which shows a quantity of "
            "'5 count'. Click the '+' button next to it once to increase "
            "the quantity. Wait a moment for the update to complete."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
    assert item.quantity == Decimal("6")


async def test_decrement_item_quantity(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory_with_quantities: dict,
) -> None:
    """Verify that clicking - on a quantity stepper decrements the value."""
    item = seeded_inventory_with_quantities["items"][0]  # Red Jacket, qty=5

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Find the item '{ITEM_RED_JACKET}' which shows a quantity of "
            "'5 count'. Click the minus '\u2212' button next to it once to "
            "decrease the quantity. Wait a moment for the update to complete."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
    assert item.quantity == Decimal("4")


async def test_set_item_quantity_inline(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory_with_quantities: dict,
) -> None:
    """Verify inline editing of a quantity value by clicking on the number."""
    item = seeded_inventory_with_quantities["items"][0]  # Red Jacket, qty=5

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Find the item '{ITEM_RED_JACKET}'. Click directly on the "
            "quantity text '5 count' (not the +/- buttons, but the number "
            "itself). An input field should appear. Clear it, type '10', "
            "and press Enter. Wait a moment for the update to complete."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
    assert item.quantity == Decimal("10")


# ---------------------------------------------------------------------------
# Item creation tests
# ---------------------------------------------------------------------------


async def test_create_item_manual(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify creating an item via manual form entry (no image upload)."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Add' in the bottom "
            "navigation. On the add item page, click 'Skip and enter "
            "manually' to show the form. Fill in the name as "
            f"'{NEW_ITEM_MANUAL}' and the description as "
            f"'{NEW_ITEM_MANUAL_DESC}'. Select '{UNIT_GARAGE}' as the "
            "unit. Click the 'Add Item' button to submit the form."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert await sync_to_async(Item.objects.filter(name=NEW_ITEM_MANUAL).exists)()


async def test_create_item_with_image(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify creating an item with image upload and AI auto-fill."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Add' in the bottom "
            "navigation. Upload the image file at "
            f"'{TEST_IMAGE_PATH}' using the file input on the page. "
            "Wait for the AI to analyze the image and auto-fill the "
            "form fields. The name and description should be "
            f"auto-populated. Select '{UNIT_GARAGE}' as the unit. "
            "Click the 'Add Item' button to submit."
        ),
        available_file_paths=[str(TEST_IMAGE_PATH)],
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert await sync_to_async(Item.objects.filter(name=NEW_ITEM_AI).exists)()


async def test_create_item_with_quantity(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify creating an item with quantity fields set."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Add' in the bottom "
            "navigation. Click 'Skip and enter manually' to show the "
            f"form. Fill in the name as '{NEW_ITEM_MANUAL}' and "
            f"description as '{NEW_ITEM_MANUAL_DESC}'. Select "
            f"'{UNIT_GARAGE}' as the unit. In the Quantity section, "
            "select 'Count' as the measurement type, enter '3' as the "
            "amount, and select 'Count' as the unit. Click 'Add Item' "
            "to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    item = await sync_to_async(Item.objects.get)(name=NEW_ITEM_MANUAL)
    assert item.quantity == Decimal("3")
    assert item.quantity_unit == "count"


# ---------------------------------------------------------------------------
# Item edit / move / delete variations
# ---------------------------------------------------------------------------


async def test_edit_item_description(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify editing an item's description from the unit detail page."""
    item = seeded_inventory["items"][1]  # Screwdriver Set
    new_description = "Complete 32-piece set with case"

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Click on the item '{ITEM_SCREWDRIVER}' to open its details. "
            "In the detail sheet, click the edit button (pencil icon). "
            "In the edit dialog, change the description to "
            f"'{new_description}' and click 'Save'."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
    assert item.description == new_description


async def test_move_item_to_different_unit(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify moving an item to a different unit via the bottom sheet."""
    item = seeded_inventory["items"][0]  # Red Jacket in Garage Shelf
    target_unit = seeded_inventory["units"][1]  # Bedroom Closet

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
            f"Click on the item '{ITEM_RED_JACKET}' to open its details. "
            "In the detail sheet that slides up, click the move button "
            "(the arrow icon). In the move dialog, select "
            f"'{UNIT_CLOSET}' as the target unit and click 'Move'."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    await sync_to_async(item.refresh_from_db)()
    assert item.unit_id == target_unit.id


async def test_delete_item_from_detail_page(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
) -> None:
    """Verify deleting an item from the full item detail page."""
    item = seeded_inventory["items"][4]  # Headphones in Desk Drawer
    item_id = item.id

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on '{LOCATION_OFFICE}', then click on '{UNIT_DESK}'. "
            f"Click on the item '{ITEM_HEADPHONES}' to open its details. "
            "In the detail sheet, click 'View full details' to go to the "
            "full item page. On that page, click the three-dot menu icon "
            "in the top-right corner, then click 'Delete'. "
            "Confirm the deletion when prompted."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    assert not await sync_to_async(Item.objects.filter(id=item_id).exists)()


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


async def test_duplicate_item_name_rejected(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,  # noqa: ARG001
) -> None:
    """Verify that creating an item with a duplicate name is rejected."""
    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and click 'Add' in the bottom "
            "navigation. Click 'Skip and enter manually' to show the "
            f"form. Fill in the name as '{ITEM_RED_JACKET}' and "
            f"description as 'Another jacket'. Select '{UNIT_CLOSET}' "
            "as the unit. Click 'Add Item' to submit."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)
    # Should still be exactly 1 item named "Red Jacket"
    count = await sync_to_async(Item.objects.filter(name=ITEM_RED_JACKET).count)()
    assert count == 1
