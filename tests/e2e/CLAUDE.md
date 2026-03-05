# E2E Tests — Browser-Use + AWS Bedrock

## Overview

E2E tests use [Browser-Use](https://github.com/browser-use/browser-use) v0.12.1 to drive a real browser against a live Django test server. An LLM (Claude via AWS Bedrock) interprets task instructions and executes browser actions autonomously.

Two LLMs are in play during tests:
- **Browser-Use agent LLM** (real) — drives the browser, configured in `config.yaml`
- **WMS app LLM** (mocked) — the app's own AI features are patched via `mock_wms_llm` to avoid cost and flakiness

## Assertion Design Principles

### Prefer deterministic assertions over LLM text parsing

The agent's natural language output (`result.final_result()`) is non-deterministic. Assertions against it are fragile and produce false positives/negatives. Always prefer verifiable signals:

| Signal | How to access | Use for |
|--------|--------------|---------|
| **Final URL** | `result.history[-1].state.url` | Login redirects, page navigation |
| **Database state** | Django ORM queries (wrap with `sync_to_async`) | CRUD operations |
| **HTTP status** | Check URL didn't land on an error page | Error detection |

**Good** — assert on the URL after login:
```python
result = await agent.run(max_steps=DEFAULT_MAX_STEPS)
final_url = result.history[-1].state.url
assert final_url.rstrip("/") == live_server.url
```

**Good** — assert on database state after a create:
```python
await agent.run(max_steps=DEFAULT_MAX_STEPS)
assert await sync_to_async(Location.objects.filter(name="Test Garage").exists)()
```

**Avoid** — parsing the agent's summary text:
```python
# Fragile: depends on how the LLM phrases its response
final_text = result.final_result().lower()
assert "home" in final_text
```

Text-based assertions are acceptable only when no deterministic signal exists (e.g., verifying that a visual element is present on a page where no URL or DB change occurs).

### Keep task instructions minimal

Tell the agent *what to do*, not *what to report back*. Shorter tasks reduce token usage and give the LLM less room to misinterpret.

```python
# Good: action-only instruction
"Go to {url}/login/ and log in with email '...' and password '...'. After logging in, you are done."

# Avoid: asking the agent to narrate
"Go to {url}/login/ and log in. Tell me what page you ended up on and describe what you see."
```

### Wrap Django ORM calls with `sync_to_async`

All tests are `async`. Django ORM is synchronous. Use `asgiref.sync.sync_to_async` for any ORM assertion:

```python
from asgiref.sync import sync_to_async

await sync_to_async(item.refresh_from_db)()
assert not await sync_to_async(Item.objects.filter(id=item_id).exists)()
```

## Infrastructure

### Fixtures (conftest.py)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `_use_plain_staticfiles_storage` | session | Swaps manifest storage for plain `StaticFilesStorage` so the live server can serve CSS/JS |
| `browser_use_llm` | session | `_FullSchemaChatBedrock` instance configured from `config.yaml` |
| `browser_instance` | function | Headless Chromium browser (390x844 viewport) |
| `agent_factory` | function | Creates `Agent` instances pre-configured for the live server |
| `authenticated_agent_factory` | function | Wraps `agent_factory` with login instructions prepended to the task |
| `e2e_test_user` | function, autouse | Creates a fresh test user for each test |
| `seeded_inventory` | function | Creates 2 locations, 3 units, 5 items for browse/search tests |
| `mock_wms_llm` | function, autouse | Mocks WMS internal LLM calls |

### Configuration

- `config.yaml` (git-ignored) — Bedrock model ID and region. Copy `config.yaml.example` to get started.
- Model must use a cross-region inference profile ID (e.g., `us.anthropic.claude-sonnet-4-20250514-v1:0`), not a bare model ID.

### Agent settings

- `enable_planning=False` — Bedrock's converse API can't handle the planning schema fields
- `flash_mode=True` — strips plan-related fields from the output schema
- `_FullSchemaChatBedrock` — custom subclass that resolves `$ref`/`$defs` and merges `anyOf` discriminated unions into Bedrock-compatible schemas

### Database

pytest-django creates an ephemeral `test_` database on the local PostgreSQL server. All tests use `transaction=True` (required for `live_server` since the browser hits the server from a separate thread that needs committed data). Tables are flushed between tests.

### Static files

CSS and JS are served from each app's `static/` directory via Django's `StaticFilesHandler` (finders). The `_use_plain_staticfiles_storage` fixture swaps the production `CompressedManifestStaticFilesStorage` for plain `StaticFilesStorage` so URLs aren't hashed. No `collectstatic` needed.

### Authentication

Login is done via task instructions, not `initial_actions`. Browser-Use's `navigate` action has `terminates_sequence=True`, which aborts any remaining `initial_actions` in the same batch. Prepending login steps to the task string lets the agent handle login across multiple steps.

## Running

```bash
make test-e2e              # Headless
make test-e2e-headed       # Visible browser (debugging)
make install-e2e           # First-time dependency setup
```

### Centralize test data in `conftest.py`

All shared test data — seeded inventory names, step limits, directory paths — lives in `conftest.py` as module-level constants. Test files import these constants instead of using string literals.

**Constants available:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_MAX_STEPS` | `25` | Default step limit for all tests |
| `SCREENSHOTS_DIR` | `tests/e2e/screenshots/` | Screenshot output directory |
| `LOCATION_HOUSE` | `"My House"` | Seeded location name |
| `LOCATION_OFFICE` | `"Office"` | Seeded location name |
| `UNIT_GARAGE` | `"Garage Shelf"` | Seeded unit name |
| `UNIT_CLOSET` | `"Bedroom Closet"` | Seeded unit name |
| `UNIT_DESK` | `"Desk Drawer"` | Seeded unit name |
| `ITEM_RED_JACKET` | `"Red Jacket"` | Seeded item name |
| `ITEM_SCREWDRIVER` | `"Screwdriver Set"` | Seeded item name |
| `ITEM_BOOTS` | `"Winter Boots"` | Seeded item name |
| `ITEM_CHARGER` | `"Laptop Charger"` | Seeded item name |
| `ITEM_HEADPHONES` | `"Headphones"` | Seeded item name |

**Good** — import and use constants:
```python
from .conftest import DEFAULT_MAX_STEPS, ITEM_RED_JACKET, LOCATION_HOUSE, UNIT_GARAGE

agent = authenticated_agent_factory(
    task=(
        f"Click on '{LOCATION_HOUSE}', then click on '{UNIT_GARAGE}'. "
        f"Find the item called '{ITEM_RED_JACKET}'."
    ),
)
result = await agent.run(max_steps=DEFAULT_MAX_STEPS)
```

**Avoid** — hardcoding values in test files:
```python
# Bad: duplicates the value and drifts if conftest changes
agent = authenticated_agent_factory(
    task="Click on 'My House', then click on 'Garage Shelf'. Find 'Red Jacket'.",
)
result = await agent.run(max_steps=25)
```

When adding new seeded data, define the constant in `conftest.py` first, use it in the fixture, then import it in test files.

## Common Pitfalls

- **Stale test DB** — If a previous run crashed, `test_` may still exist with active connections. Fix: `psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_';" && psql -d postgres -c "DROP DATABASE test_;"`
- **Rate limiting** — Opus models have low daily token limits on Bedrock. Sonnet is more practical for iterative test runs.
- **`SynchronousOnlyOperation`** — Calling sync ORM from an async test. Always use `sync_to_async`.
