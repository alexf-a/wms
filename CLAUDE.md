# WMS — Warehouse Management System

## Purpose

WMS is a web-native app for organizing personal belongings. It solves two pain points:

1. **Storage unit transparency** — knowing what items exist in bins, lockers, sheds, etc.
2. **Item location** — finding where a particular item is stored.

WMS addresses these through a digital inventory system and LLM-powered search (natural language and image inputs).

## Tech Stack

- **Backend:** Django (Python)
- **Frontend:** Django templates + Tailwind CSS v4 (standalone CLI, no Node.js) + vanilla JS
- **LLM:** LangChain with AWS Bedrock (Claude models)
- **Database:** PostgreSQL-compatible
- **Environment:** Poetry for dependency management
- **Deployment:** AWS Lightsail Container Service
- **Static files:** S3 bucket
- **Tool versions:** Pinned in `.tool-versions` — Makefile and Dockerfile read from it automatically

## Project Structure

- `core/` — Django app: models, views, forms, templates, static assets, management commands
- `core/tailwind/input.css` — Tailwind v4 theme tokens and design system (`@theme` block)
- `core/llm_calls/` — JSON files defining LLM call parameters (system prompts, human prompts)
- `core/templates/core/` — Django templates (all extend `base.html`)
- `core/static/core/js/` — Client-side JavaScript modules
- `llm/` — LLM functionality (search, item generation, handler)
- `aws_utils/` — AWS boto3 utilities
- `schemas/` — Pydantic data schemas
- `deploy/` — Deployment configuration (containers.json, public-endpoint.json)
- `tests/` — pytest test suite

## Common Commands

```bash
# Development
poetry run python manage.py runserver        # Run dev server
make tw-watch                                # Tailwind watch mode
make tw-build                                # One-shot Tailwind build

# Testing
poetry run pytest                            # Run all Python tests
make test-js                                 # Run all JavaScript tests

# Deployment
make local-up                                # Local HTTP dev server (Docker)
make local-https                             # Local HTTPS prod testing (Docker + Caddy)
make up                                      # Build, push, deploy to Lightsail

# Utilities
poetry run python manage.py collectstatic    # Collect static files
```

## Development Guidelines

- **Python:** Type annotations on all parameters and return types. Ruff-compatible code. Google-style docstrings on public methods and classes.
- **JavaScript:** JSDoc on all functions (`@param`/`@returns`) and file-level comments on new files.
- **Templates:** Extend `base.html`. Use Tailwind utility classes with semantic tokens. No inline styles.
- **Dependencies:** Update `pyproject.toml` via Poetry. Run all commands with `poetry run`.
- **Testing:** pytest with `test_*.py` naming. All features and bug fixes need test coverage.
- **Tailwind CSS:** Theme defined in `core/tailwind/input.css`. Use `make tw-build` or `make tw-watch`.
- **Tool versions:** Update `.tool-versions` — Makefile and Dockerfile propagate automatically.

## Coding Practices

1. Make smaller, incremental changes. Ask for feedback between changes.
2. Clean up all testing and debugging code after implementation.
3. When debugging, search the web first (GitHub Issues, Stack Overflow).
4. When using AWS CLI, ensure the cli-pager is disabled.

## Additional Context

- UI/UX design system and component patterns: @core/CLAUDE.md
- LLM infrastructure (search, item generation): @llm/CLAUDE.md
