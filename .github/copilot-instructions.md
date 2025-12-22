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
- **Poetry**: Use Poetry for environment management, project configuration and to run scripts and tests. Ensure that the `pyproject.toml` file is updated with any new dependencies. Run all commands and scripts with `poetry run`
- **Ruff**: Use Ruff for linting and code quality checks. Follow the project's linting rules and fix any issues reported by Ruff.
- **Google Docstrings**: Use Google-style docstrings for all public methods and classes.
- **Testing**: All tests are written using pytest. Use the `test_*.py` naming convention for test files and organize tests in the `tests/` directory. Ensure that all new features and bug fixes are covered by tests.
- **Debugging**:
   - Always search the web first for similar issues and solutions, using resources like GitHub Issues, Stack Overflow, etc.
   - When using the AWS CLI to produce outputs, ensure that the cli-pager is disabled.

## Coding Instructions
1. Make smaller, incremental changes to the codebase. Make these changes one-at-a-time, then ask for feedback.
2. Clean up all testing and debugging code after implementation goals have been met.

## Deployment Process (Lightsail Containers)

This project deploys to AWS Lightsail Container Service using a container image built from the repository. Configuration is environment‑driven and centralized.

### Key Files
- `Dockerfile`: Builds the production image (Poetry install, collectstatic, non‑root user).
- `docker-entrypoint.sh`: Runtime bootstrap (verifies `PORT` env, runs migrations opportunistically, then `gunicorn`).
- `gunicorn.conf.py`: Server tuning (workers via `WEB_CONCURRENCY` override or `(2*cores)+1`, threading, timeouts, logging). Also ensures `DJANGO_SETTINGS_MODULE` is set from the environment.
- `deploy/containers.example.json`: Template for the real (ignored) `deploy/containers.json` containing env vars (single source of truth for `PORT`, `DEBUG`, `ALLOWED_HOSTS`, `SECRET_KEY`, DB_* vars, `DJANGO_SETTINGS_MODULE`, optional `WEB_CONCURRENCY`).
- `deploy/public-endpoint.json`: Defines public endpoint and health check path (update to `/healthz/` if you switch from `/`).
- `Makefile`: Automation targets for build & deploy (`docker-build`, `create`, `push`, `deploy`, `up`, `down`, `setup`, `install-lightsailctl-fix`). Includes workarounds for lightsailctl bugs #95 and #100. Validates presence of `deploy/containers.json` before deploy. Uses patched lightsailctl and explicit linux/amd64 platform.
- `core/views.py` & `core/urls.py`: Provide the lightweight health check endpoint at `/healthz/` (JSON `{"status": "ok"}`).

### Build & Deploy Workflow

**IMPORTANT**: The official lightsailctl has bugs that prevent image pushing. Use the patched version from [PR #102](https://github.com/aws/lightsailctl/pull/102).

#### Prerequisites
1. Install patched lightsailctl: `make install-lightsailctl-fix`
2. Ensure `deploy/containers.json` exists (real secrets file, ignored by git).

#### Deployment Steps
1. **First-time setup**: 
   - Run `make install-lightsailctl-fix`
   - Run `make create` with your desired args.
   - Update `HOST_SUFFIX` in `Makefile` to use the URL from the output. Use the suffix after the service name (e.g. `us-west-2.cs.amazonlightsail.com`)
   - Run `make up`
2. **Regular deployments**: `make up` (builds, pushes, and deploys)
3. **Local development (HTTP)**: `make local-up` or `make local-up ENV_FILE=.env.local`
4. **Local production testing (HTTPS)**: `make local-https` (see Local Production Testing section)

Note: `make` commands will modify your containers.json file.

#### Stopping Local Servers
- **HTTP mode**: `make local-down`
- **HTTPS mode**: `make local-https-down`

#### Manual Steps
1. Build image with correct platform: `make docker-build` (uses linux/amd64)
2. Create service (first time): `make create`
3. Get the URL from the Lightsail console output, and add it as `ALLOWED_HOSTS` in `deploy/containers.json`.
4. Push image to Lightsail registry: `make push` (uses patched lightsailctl)
5. Deploy new version: `make deploy`
6. Tear down (stop billing): `make down` (deletes service; recreate later with `make create && make deploy`).

#### Storage
Static files are stored in an S3 bucket. See `settings.py` for configuration.

#### Troubleshooting
- If you get "image push response does not contain the image digest" error, run `make install-lightsailctl-fix`
- The Makefile automatically uses `--platform linux/amd64` to ensure Lightsail compatibility
- Patched lightsailctl is installed to `~/go/bin/` and automatically added to PATH

## Local Development (HTTP)

For local development and debugging with `DEBUG=True`, use HTTP mode which runs only the Django web service.

### Key Files
- `.env.local.example`: Template for creating `.env.local` with mobile testing configuration.
- `docker-compose.yml`: Defines the `web` service for Django.
- `Makefile`: Automation targets (`local-up`, `local-down`).

### Prerequisites
1. Copy `.env.local.example` to `.env.local` and fill in values.
2. Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` with your Mac's IP address (find it with `ipconfig getifaddr en0`).

### Workflow

#### Start Local HTTP Server
```bash
make local-up ENV_FILE=.env.local
```
This will:
- Start only the Django web service (no Caddy)
- Run in `DEBUG=True` mode
- Be accessible at `http://localhost:8000` or `http://<your-ip>:8000` for mobile

#### Stop Local HTTP Server
```bash
make local-down
```

### Troubleshooting: Browser Forcing HTTPS
If you previously used `make local-https`, your browser may have cached HSTS (HTTP Strict Transport Security) settings and automatically redirect HTTP to HTTPS. To fix:

- **Chrome/Edge**: Visit `chrome://net-internals/#hsts`, enter `localhost` in "Delete domain security policies", click Delete
- **Firefox**: Clear browsing data, specifically "Active Logins"
- **Safari**: Quit Safari, delete `~/Library/Cookies/HSTS.plist`, restart Safari
- **Alternative**: Access via IP address instead of `localhost` (e.g., `http://192.168.x.x:8000`)

## Local Production Testing (HTTPS)

Test the app locally in production mode (`DEBUG=False`) with HTTPS via Caddy reverse proxy. This is useful for testing production security settings and mobile device compatibility.

### Key Files
- `Caddyfile`: Reverse proxy config with automatic TLS certificate generation. Uses `{$HTTP_PORT}` and `{$HTTPS_PORT}` for port configuration.
- `.env.local.https.example`: Template for creating `.env.local.https`.
- `deploy/generate_qr.py`: Generates QR codes for mobile access and CA certificate download.
- `Makefile`: Automation targets for local HTTPS setup (`local-https`, `caddy-trust`, `caddy-export-ca`, `local-https-down`).
- `docker-compose.yml`: Passes environment variables to Caddy container for port and domain configuration.

### Prerequisites
1. Copy `.env.local.https.example` to `.env.local.https` and fill in values.
2. Update `DOMAIN` to your Mac's hostname: `hostname` (e.g., `alexs-macbook-pro.local`)
3. Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to match your `DOMAIN`
4. (Optional) Customize `HTTP_PORT` (default: 8080) and `HTTPS_PORT` (default: 8443)

### Workflow

#### Start Local HTTPS Server
```bash
make local-https
```
This will:
- Validate environment configuration
- Start Django and Caddy containers
- Auto-install Caddy CA on first run (for desktop browser trust)
- Display QR code for mobile access

**Access Points:**
- Desktop: `https://<DOMAIN>:<HTTPS_PORT>` (e.g., `https://alexs-macbook-pro.local:8443`)
- Desktop (HTTP redirect): `http://<DOMAIN>:<HTTP_PORT>` (e.g., `http://alexs-macbook-pro.local:8080` redirects to HTTPS)
- Mobile: Same URLs - works via mDNS/Bonjour

**Note:** Default ports are 8080 (HTTP) and 8443 (HTTPS). These can be customized in `.env.local.https`.

#### Mobile Device Setup (One-Time)
Mobile devices need to trust the Caddy CA certificate:

```bash
make caddy-export-ca
```

This extracts the CA, starts an HTTP server, and displays a QR code. On your mobile device:

1. Scan the QR code or visit `http://<DOMAIN>:8888/caddy-root-ca.crt` (port 8888 is fixed for CA download)
2. **iOS**: Settings → Profile Downloaded → Install → Settings → General → About → Certificate Trust Settings → Enable trust
3. **Android**: Settings → Security → Install from storage → Select certificate

#### Stop Server
```bash
make local-https-down
```

**Note**: Docker volumes (containing Caddy CA certificate) are preserved by default. To completely remove them: `docker volume rm wms_caddy_data wms_caddy_config`

### AI-Enabled Workflows
There are two workflows that are AI enabled.

1) Item creation. See .github/instructions/item-addition.instructions.md
2) Item search. See .github/instructions/item-search.instructions.md

