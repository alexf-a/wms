---
applyTo: '**'
---
## Code Base Purpose

This code-base is for a web-native app for organizing personal belgongings. The app is called WMS. 

Personal storage comes with two major pain points:
1) Storage unit transparency: We are unsure what items exist in individual units of storage (such as bins, lockers, sheds, etc.)
2) Individual item location: We are unsure of the whereabouts of particular items. 

WMS seeks to address both pain-points:
1) Storage unit transparency is increased through a simple digital inventory system
2) Items are located through advanced search capabilities, using image and natural language inputs for user convenience. The current search implementation uses LLMs. 

## Code Base Organization
- `core/*`: Core Django functionality, data models, migrations and scripts/artifacts for management commands
- `core/llm_calls/*`: JSON files that define LLM calls, including system prompts, human prompts, and other parameters for LLM queries
- `aws_utils/*`: Utilities for interacting with AWS through boto3
- `llm/*`: LLM functionality.
- `schemas/*`: Data-schemas (represented as Pydantic Models) for different kinds of data, including synthetic data generating. 

## Development Guidelines
- **Django Core**: Follow Django best practices for models, views, and forms.
- **LLM Functionality**: Use the LLMHandler for all LLM queries, and ensure that LLMCall objects are used to encapsulate query parameters.
- **Poetry**: Use Poetry for environment management, project configuration and to run scripts and tests. Ensure that the `pyproject.toml` file is updated with any new dependencies. Run all commands and scrips with `poetry run`
- **Ruff**: Use Ruff for linting and code quality checks. Follow the project's linting rules and fix any issues reported by Ruff.
- **Google Docstrings**: Use Google-style docstrings for all public methods and classes.
- **Testing**: All tests are written using pytest. Use the `test_*.py` naming convention for test files and organize tests in the `tests/` directory. Ensure that all new features and bug fixes are covered by tests.

## Coding Instructions
1. Make smaller, incremental changes to the codebase. Make these changes one-at-a-time, then ask for feedback.
2. Clean up all testing and debugging code after implementation goals have been met.

## Deployment Process (Lightsail Containers)

This project deploys to AWS Lightsail Container Service using a container image built from the repository. Configuration is environment‑driven and centralized.

### Key Files
- `Dockerfile`: Builds the production image (Poetry install, collectstatic, non‑root user).
- `docker-entrypoint.sh`: Runtime bootstrap (verifies `PORT` env, runs migrations opportunistically, then `gunicorn`).
- `gunicorn.conf.py`: Server tuning (workers via `WEB_CONCURRENCY` override or `(2*cores)+1`, threading, timeouts, logging). Also ensures `DJANGO_SETTINGS_MODULE` is set from the environment.
- `lightsail/containers.example.json`: Template for the real (ignored) `lightsail/containers.json` containing env vars (single source of truth for `PORT`, `DEBUG`, `ALLOWED_HOSTS`, `SECRET_KEY`, DB_* vars, `DJANGO_SETTINGS_MODULE`, optional `WEB_CONCURRENCY`).
- `lightsail/public-endpoint.json`: Defines public endpoint and health check path (update to `/healthz/` if you switch from `/`).
- `Makefile`: Automation targets for build & deploy (`docker-build`, `create`, `push`, `deploy`, `up`, `down`, `setup`, `install-lightsailctl-fix`). Includes workarounds for lightsailctl bugs #95 and #100. Validates presence of `lightsail/containers.json` before deploy. Uses patched lightsailctl and explicit linux/amd64 platform.
- `core/views.py` & `core/urls.py`: Provide the lightweight health check endpoint at `/healthz/` (JSON `{"status": "ok"}`).

### Build & Deploy Workflow

**IMPORTANT**: The official lightsailctl has bugs that prevent image pushing. Use the patched version from [PR #102](https://github.com/aws/lightsailctl/pull/102).

#### Prerequisites
1. Install patched lightsailctl: `make install-lightsailctl-fix`
2. Ensure `lightsail/containers.json` exists (real secrets file, ignored by git).

#### Deployment Steps
1. **First-time setup**: 
   - Run `make setup` (installs patched lightsailctl, builds, creates service)
   - Update `ALLOWED_HOSTS` in `lightsail/containers.json` with the URL from the output
   - Run `make setup-deploy` (pushes and deploys)
2. **Regular deployments**: `make up` (builds, pushes, and deploys)
3. **Local deployment (debugging)**: `make local-up`

#### Manual Steps
1. Build image with correct platform: `make docker-build` (uses linux/amd64)
2. Create service (first time): `make create`
3. Get the URL from the Lightsail console output, and add it as `ALLOWED_HOSTS` in `lightsail/containers.json`.
4. Push image to Lightsail registry: `make push` (uses patched lightsailctl)
5. Deploy new version: `make deploy`
6. Tear down (stop billing): `make down` (deletes service; recreate later with `make create && make deploy`).

#### Troubleshooting
- If you get "image push response does not contain the image digest" error, run `make install-lightsailctl-fix`
- The Makefile automatically uses `--platform linux/amd64` to ensure Lightsail compatibility
- Patched lightsailctl is installed to `~/go/bin/` and automatically added to PATH

