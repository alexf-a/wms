"""E2E tests for sharing flows (unit and location)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from core.models import LocationSharedAccess, UnitSharedAccess, WMSUser

from .conftest import DEFAULT_MAX_STEPS, LOCATION_HOUSE, UNIT_GARAGE

if TYPE_CHECKING:
    from collections.abc import Callable

    from browser_use import Agent
    from django.test.utils import LiveServer

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

SHARE_RECIPIENT_EMAIL = "shared-user@example.com"


@pytest.fixture
def share_recipient(db: None) -> WMSUser:  # noqa: ARG001
    """Create a second user to be the share recipient."""
    return WMSUser.objects.create_user(
        email=SHARE_RECIPIENT_EMAIL,
        password="TestPass123!secure",
        has_completed_onboarding=True,
    )


async def test_share_unit_from_detail_page(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
    share_recipient: WMSUser,
) -> None:
    """Verify that a user can share a unit via the unit detail page."""
    garage = seeded_inventory["units"][0]  # Garage Shelf

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Click on the '{LOCATION_HOUSE}' location card to expand it. "
            f"Click on the '{UNIT_GARAGE}' unit card to go to its detail page. "
            "On the unit detail page, click the share icon button "
            "(it's in the header, next to the edit/QR buttons). "
            "A sharing dialog will open. "
            f"Type '{SHARE_RECIPIENT_EMAIL}' in the email input field. "
            "Leave the permission as 'View'. "
            "Click the 'Invite' button to share. "
            "Wait for the success message to appear."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    @sync_to_async
    def _check_share() -> bool:
        return UnitSharedAccess.objects.filter(
            user=share_recipient, unit=garage, permission="read",
        ).exists()

    assert await _check_share(), (
        f"Expected UnitSharedAccess for {SHARE_RECIPIENT_EMAIL} on {UNIT_GARAGE}"
    )


async def test_share_location_from_browse_page(
    authenticated_agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    seeded_inventory: dict,
    share_recipient: WMSUser,
) -> None:
    """Verify that a user can share a location via the browse page context menu."""
    house = seeded_inventory["locations"][0]  # My House

    agent = authenticated_agent_factory(
        task=(
            f"Go to {live_server.url} and navigate to the browse page "
            "(click 'See' in the bottom navigation). "
            f"Find the '{LOCATION_HOUSE}' location card. "
            "Click the three-dot menu button (⋮) on that card. "
            "In the menu that appears, click 'Share'. "
            "A sharing dialog will open. "
            f"Type '{SHARE_RECIPIENT_EMAIL}' in the email input field. "
            "Change the permission dropdown from 'View' to 'Edit own'. "
            "Click the 'Invite' button to share. "
            "Wait for the success message to appear."
        ),
    )
    await agent.run(max_steps=DEFAULT_MAX_STEPS)

    @sync_to_async
    def _check_share() -> bool:
        return LocationSharedAccess.objects.filter(
            user=share_recipient, location=house, permission="write",
        ).exists()

    assert await _check_share(), (
        f"Expected LocationSharedAccess for {SHARE_RECIPIENT_EMAIL} on {LOCATION_HOUSE}"
    )
