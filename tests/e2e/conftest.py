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
from browser_use.llm.aws.chat_bedrock import ChatAWSBedrock
from pydantic import BaseModel

from core.models import Item, Location, Unit, WMSUser
from schemas.item_generation import GeneratedItem
from schemas.llm_search import ItemLocation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from django.test.utils import LiveServer

# All tests in this directory get the e2e marker automatically.
pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session", autouse=True)
def _use_plain_staticfiles_storage(django_test_environment: None) -> None:  # noqa: ARG001, PT005
    """Swap CompressedManifestStaticFilesStorage for plain StaticFilesStorage.

    The manifest backend hashes filenames (e.g. tailwind.abc123.css).
    The live_server's StaticFilesHandler resolves URLs via finders, which
    only know the *original* filename — so it 404s on the hashed name.
    Switching to StaticFilesStorage produces unhashed URLs that the
    finders can resolve directly.
    """
    from django.conf import settings

    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

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


def _resolve_schema_refs(schema: dict) -> dict:
    """Resolve ``$ref`` references in a JSON schema, inlining ``$defs``.

    Bedrock's ``converse`` API does not support ``$ref``/``$defs`` or
    ``anyOf``. This function walks the schema recursively, replaces
    ``$ref`` pointers with the referenced definition, and converts
    ``anyOf`` unions into Bedrock-compatible representations:

    - **Nullable types** (``anyOf`` with a ``null`` branch): picks the
      non-null branch.
    - **Discriminated unions** (``anyOf`` with multiple object branches
      that each have a unique ``required`` field): merges all branches
      into a single object with all properties optional and a
      description listing available action types.
    """
    defs = schema.pop("$defs", {})

    def _resolve(node: Any) -> Any:  # noqa: ANN401
        if isinstance(node, dict):
            # Replace $ref with the referenced definition
            if "$ref" in node:
                ref_path = node["$ref"]  # e.g. "#/$defs/ActionModel"
                ref_name = ref_path.rsplit("/", 1)[-1]
                if ref_name in defs:
                    return _resolve(defs[ref_name].copy())
                return {"type": "object"}

            if "anyOf" in node:
                branches = node["anyOf"]
                non_null = [b for b in branches if b.get("type") != "null"]

                if not non_null:
                    return {"type": "string"}

                # Nullable type: anyOf with exactly one non-null branch
                if len(non_null) == 1:
                    resolved = _resolve(non_null[0].copy())
                    if "default" in node:
                        resolved["default"] = node["default"]
                    return resolved

                # Discriminated union: multiple object branches, each with
                # a unique required field (e.g. action types).
                # Merge all branches into one object with all props optional.
                resolved_branches = [_resolve(b.copy()) for b in non_null]
                all_objects = all(
                    b.get("type") == "object" for b in resolved_branches
                )
                if all_objects:
                    merged_props: dict[str, Any] = {}
                    action_names: list[str] = []
                    for branch in resolved_branches:
                        props = branch.get("properties", {})
                        for prop_name, prop_schema in props.items():
                            if prop_name not in merged_props:
                                merged_props[prop_name] = prop_schema
                                action_names.append(prop_name)
                    return {
                        "type": "object",
                        "properties": merged_props,
                        "description": (
                            "Provide exactly ONE of: "
                            + ", ".join(action_names)
                        ),
                    }

                # Fallback: pick first non-null branch
                resolved = _resolve(non_null[0].copy())
                if "default" in node:
                    resolved["default"] = node["default"]
                return resolved

            return {k: _resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(schema)


class _FullSchemaChatBedrock(ChatAWSBedrock):
    """``ChatAWSBedrock`` with proper JSON schema conversion for Bedrock.

    The base ``_format_tools_for_request`` flattens the Pydantic schema to
    only top-level ``{type, description}`` pairs, losing all nested
    structure. This causes the model to generate invalid action names
    (e.g. ``scroll_down`` instead of ``scroll``) because the tool schema
    doesn't describe the action discriminated union.

    This subclass resolves ``$ref``/``$defs``, simplifies ``anyOf``, and
    passes the full nested schema to Bedrock's ``converse`` API.
    """

    def _format_tools_for_request(
        self, output_format: type[BaseModel],
    ) -> list[dict[str, Any]]:
        schema = output_format.model_json_schema()
        resolved = _resolve_schema_refs(schema)

        # Remove Pydantic metadata that Bedrock doesn't accept
        _strip_unsupported_keys(resolved)

        return [
            {
                "toolSpec": {
                    "name": f"extract_{output_format.__name__.lower()}",
                    "description": (
                        f"Extract information in the format of "
                        f"{output_format.__name__}"
                    ),
                    "inputSchema": {"json": resolved},
                },
            },
        ]


def _strip_unsupported_keys(node: Any) -> None:  # noqa: ANN401
    """Recursively remove JSON schema keys that Bedrock doesn't support."""
    unsupported = {"title", "additionalProperties", "default"}
    if isinstance(node, dict):
        for key in unsupported & node.keys():
            del node[key]
        for v in node.values():
            _strip_unsupported_keys(v)
    elif isinstance(node, list):
        for item in node:
            _strip_unsupported_keys(item)


@pytest.fixture(scope="session")
def browser_use_llm() -> _FullSchemaChatBedrock:
    """Create the LLM instance for Browser-Use agent (AWS Bedrock).

    Uses a subclass of Browser-Use's ``ChatAWSBedrock`` that passes the
    full resolved JSON schema to Bedrock's ``converse`` API, giving the
    model proper information about available actions and their parameters.

    This LLM drives the browser agent. It is NOT the same as the WMS app's
    internal LLM calls (those are mocked via ``mock_wms_llm``).
    """
    config = _load_e2e_config()
    bedrock_config = config["bedrock"]
    return _FullSchemaChatBedrock(
        model=bedrock_config["model"],
        aws_region=bedrock_config["region"],
        aws_sso_auth=True,
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
    await browser.stop()


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_factory(
    browser_use_llm: _FullSchemaChatBedrock,
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
            enable_planning=False,
            flash_mode=True,
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
# Authenticated agent factory (login via task instructions)
# ---------------------------------------------------------------------------


@pytest.fixture
def authenticated_agent_factory(
    agent_factory: Callable[..., Agent],
    live_server: LiveServer,
    test_user_credentials: dict[str, str],
) -> Callable[..., Agent]:
    """Create agents that log in before performing their main task.

    Prepends login instructions to the task description so the agent
    navigates to the login page, enters credentials, and submits the
    form before proceeding. This approach is necessary because
    Browser-Use's ``navigate`` action terminates ``initial_actions``
    sequences (to protect against stale DOM), preventing subsequent
    form-filling actions from executing.
    """

    def _create_authenticated_agent(task: str, **kwargs: Any) -> Agent:  # noqa: ANN401
        login_url = f"{live_server.url}/login/"
        authenticated_task = (
            f"First, go to {login_url} and log in with "
            f"email '{test_user_credentials['email']}' "
            f"and password '{test_user_credentials['password']}'. "
            f"After logging in successfully, do the following: {task}"
        )
        return agent_factory(task=authenticated_task, **kwargs)

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
