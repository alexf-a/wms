"""E2E test fixtures for Browser-Use integration.

Provides browser lifecycle management, agent factory, and authenticated
session helpers for end-to-end testing against a live Django server.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import yaml
from browser_use import Agent, Browser
from langchain_aws.chat_models.bedrock import ChatBedrock

from core.models import Item, Location, Unit, WMSUser
from schemas.item_generation import GeneratedItem
from schemas.llm_search import ItemLocation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from django.test.utils import LiveServer

# All tests in this directory get the e2e marker automatically.
pytestmark = pytest.mark.e2e

E2E_DIR = Path(__file__).parent
SCREENSHOTS_DIR = E2E_DIR / "screenshots"
_CONFIG_PATH = E2E_DIR / "config.yaml"


def _load_e2e_config() -> dict:
    """Load E2E test configuration from config.yaml.

    Returns:
        dict: Parsed YAML config.

    Raises:
        FileNotFoundError: If config.yaml does not exist, with instructions
            to copy config.yaml.example.
    """
    if not _CONFIG_PATH.exists():
        msg = (
            f"E2E config file not found: {_CONFIG_PATH}\n"
            f"Copy the example to get started:\n"
            f"  cp {_CONFIG_PATH.with_suffix('.yaml.example')} {_CONFIG_PATH}"
        )
        raise FileNotFoundError(msg)
    with _CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# LLM for Browser-Use agent (real — drives the browser)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_use_llm() -> ChatBedrock:
    """Create the LLM instance for Browser-Use agent (AWS Bedrock).

    This LLM drives the browser agent. It is NOT the same as the WMS app's
    internal LLM calls (those are mocked via ``mock_wms_llm``).
    """
    config = _load_e2e_config()
    bedrock_config = config["bedrock"]
    return ChatBedrock(
        model=bedrock_config["model"],
        region_name=bedrock_config["region"],
    )


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def browser_instance() -> AsyncGenerator[Browser, None]:
    """Create and teardown a headless Browser instance."""
    headless = os.environ.get("BROWSER_USE_HEADLESS", "true").lower() != "false"
    browser = Browser(
        headless=headless,
        window_size={"width": 390, "height": 844},  # iPhone 14 Pro
    )
    yield browser
    await browser.close()


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_factory(
    browser_use_llm: ChatBedrock,
    browser_instance: Browser,
    live_server: LiveServer,
) -> Callable[..., Agent]:
    """Create Browser-Use agents pre-configured for the live test server."""

    def _create_agent(
        task: str,
        *,
        initial_actions: list | None = None,
        max_actions_per_step: int = 4,
        use_vision: str = "auto",
        generate_gif: bool = False,
    ) -> Agent:
        return Agent(
            task=task,
            llm=browser_use_llm,
            browser=browser_instance,
            initial_actions=initial_actions,
            max_actions_per_step=max_actions_per_step,
            use_vision=use_vision,
            generate_gif=generate_gif,
            extend_system_message=(
                f"The app is running at {live_server.url}. "
                "This is a mobile-first web app with bottom tab navigation "
                "(Home, Find, Add, See). All actions happen within this "
                "single domain."
            ),
        )

    return _create_agent


# ---------------------------------------------------------------------------
# Test user + credentials
# ---------------------------------------------------------------------------

E2E_USER_EMAIL = "e2e-test@example.com"
E2E_USER_PASSWORD = "TestPass123!secure"  # noqa: S105


@pytest.fixture
def test_user_credentials() -> dict[str, str]:
    """Return credentials for the E2E test user."""
    return {"email": E2E_USER_EMAIL, "password": E2E_USER_PASSWORD}


@pytest.fixture(autouse=True)
def e2e_test_user(db: None, test_user_credentials: dict[str, str]) -> WMSUser:  # noqa: ARG001
    """Create the E2E test user in the database before each test."""
    return WMSUser.objects.create_user(
        email=test_user_credentials["email"],
        password=test_user_credentials["password"],
        has_completed_onboarding=True,
    )


# ---------------------------------------------------------------------------
# Authenticated agent factory (deterministic login via initial_actions)
# ---------------------------------------------------------------------------


@pytest.fixture
def authenticated_agent_factory(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    test_user_credentials: dict[str, str],
) -> Callable[..., Agent]:
    """Create agents that are already logged in.

    Uses ``initial_actions`` to navigate to the login page and submit
    credentials before the main task begins. This avoids spending LLM
    tokens on the authentication step.
    """

    def _create_authenticated_agent(task: str, **kwargs: Any) -> Agent:  # noqa: ANN401
        login_url = f"{live_server.url}/login/"
        login_actions = [
            {"open_url": login_url},
            {"input_text": {"index": 0, "text": test_user_credentials["email"]}},
            {"input_text": {"index": 1, "text": test_user_credentials["password"]}},
            {"click_element": {"index": 2}},  # Login button
        ]
        existing_actions = kwargs.pop("initial_actions", None) or []
        return agent_factory(
            task=task,
            initial_actions=login_actions + existing_actions,
            **kwargs,
        )

    return _create_authenticated_agent


# ---------------------------------------------------------------------------
# Seed inventory for browse / search tests
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_inventory(e2e_test_user: WMSUser) -> dict:
    """Create a realistic inventory for browse/search testing.

    Creates 2 locations, 3 units, and 5 items distributed across units.
    """
    house = Location.objects.create(
        user=e2e_test_user, name="My House", address="123 Main St",
    )
    office = Location.objects.create(user=e2e_test_user, name="Office")

    garage = Unit.objects.create(
        user=e2e_test_user, name="Garage Shelf", location=house,
    )
    closet = Unit.objects.create(
        user=e2e_test_user, name="Bedroom Closet", location=house,
    )
    desk = Unit.objects.create(
        user=e2e_test_user, name="Desk Drawer", location=office,
    )

    items = [
        Item.objects.create(
            user=e2e_test_user,
            name="Red Jacket",
            description="Winter jacket, bright red",
            unit=garage,
        ),
        Item.objects.create(
            user=e2e_test_user,
            name="Screwdriver Set",
            description="Phillips and flathead set",
            unit=garage,
        ),
        Item.objects.create(
            user=e2e_test_user,
            name="Winter Boots",
            description="Black snow boots",
            unit=closet,
        ),
        Item.objects.create(
            user=e2e_test_user,
            name="Laptop Charger",
            description="USB-C 65W charger",
            unit=desk,
        ),
        Item.objects.create(
            user=e2e_test_user,
            name="Headphones",
            description="Over-ear noise cancelling",
            unit=desk,
        ),
    ]

    return {
        "locations": [house, office],
        "units": [garage, closet, desk],
        "items": items,
    }


# ---------------------------------------------------------------------------
# Mock WMS internal LLM calls (prevent real Bedrock calls from the app)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_wms_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock all WMS internal LLM calls to avoid cost and flakiness.

    The Browser-Use agent's LLM remains real (it drives the browser).
    Only the WMS app's own LLM features are patched.
    """
    mock_generated_item = GeneratedItem(
        name="Test Item",
        description="A test item generated by mock",
    )

    mock_item_location = ItemLocation(
        item_name="Red Jacket",
        unit_name="Garage Shelf",
        confidence="High",
        additional_info="Found with high confidence (mocked)",
    )

    monkeypatch.setattr(
        "core.views.extract_item_features_from_image",
        MagicMock(return_value=mock_generated_item),
    )
    monkeypatch.setattr(
        "core.views.find_item_location",
        MagicMock(return_value=mock_item_location),
    )


# ---------------------------------------------------------------------------
# Screenshot on failure
# ---------------------------------------------------------------------------


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:  # noqa: ARG001
    """Capture browser screenshot when a test fails."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        browser = item.funcargs.get("browser_instance")
        if browser is not None:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            screenshot_path = SCREENSHOTS_DIR / f"{item.name}.png"
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Inside an async test — schedule coroutine
                    _task = loop.create_task(_capture_screenshot(browser, screenshot_path))  # noqa: RUF006
                else:
                    loop.run_until_complete(
                        _capture_screenshot(browser, screenshot_path),
                    )
            except Exception:  # noqa: BLE001, S110
                pass  # Best-effort — don't fail the report hook


async def _capture_screenshot(browser: Browser, path: Path) -> None:
    """Take a screenshot from the browser's current page."""
    if hasattr(browser, "page") and browser.page is not None:
        await browser.page.screenshot(path=str(path))
