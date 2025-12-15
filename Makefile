SVC?=wms
REGION?=us-west-2
POWER?=nano
SCALE?=1
# Path to deployment containers spec
CONTAINERS?=deploy/containers.json
 # Host suffix for ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS
HOST_SUFFIX?=csf5750j52mvw.us-west-2.cs.amazonlightsail.com
# Docker platform architecture - Lightsail only supports linux/amd64
PLATFORM?=linux/amd64
# Image tag suffix based on architecture
ARCH_TAG?=amd64

# lightsailctl bug fix: Ensure the patched version is in PATH
# The official lightsailctl has a bug with "image push response does not contain the image digest"
# We use the patched version from: https://github.com/aws/lightsailctl/pull/102
# Install with: cd /tmp && git clone https://github.com/paxan/lightsailctl.git -b paxan/image-push-bug-fixes && cd lightsailctl && go install ./...
export PATH := $(PATH):$(HOME)/go/bin

.PHONY: docker-build deploy up down create push install-lightsailctl-fix sync-env local-up update-hosts update-image local-https caddy-trust caddy-export-ca local-https-down

# =============================================================================
# Helper Functions for Local HTTPS Setup
# =============================================================================

# Validate environment file contains required variables
# Usage: $(call validate-env-file,path/to/env/file,VAR1 VAR2 VAR3)
define validate-env-file
    @echo "Validating environment file: $(1)"
    @if [ ! -f "$(1)" ]; then \
        echo "Error: Environment file not found: $(1)"; \
        exit 1; \
    fi
    @for var in $(2); do \
        if ! grep -q "^$$var=" "$(1)"; then \
            echo "Error: Required variable $$var not found in $(1)"; \
            exit 1; \
        fi; \
    done
    @echo "Environment validation passed"
endef

# Validate environment file for local HTTPS testing (with DEBUG=False check)
# Usage: $(call validate-local-https-env,path/to/env/file)
define validate-local-https-env
    $(call validate-env-file,$(1),DOMAIN ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS DEBUG)
    @if ! grep -q "^DEBUG=False" "$(1)"; then \
        echo "Error: DEBUG must be set to False in $(1) for production mode testing"; \
        exit 1; \
    fi
endef



# Check if Caddy volumes were recreated and invalidate trust sentinel
# Usage: $(call check-local-https-caddy-volumes)
define check-local-https-caddy-volumes
	@if docker volume inspect wms_caddy_data >/dev/null 2>&1; then \
		if [ -f .caddy-trusted ]; then \
			VOLUME_CREATED=$$(docker volume inspect wms_caddy_data --format '{{.CreatedAt}}' 2>/dev/null | sed 's/\..*//' | xargs -I {} date -j -f "%Y-%m-%dT%H:%M:%S" {} "+%s" 2>/dev/null); \
			if [ -n "$$VOLUME_CREATED" ]; then \
				SENTINEL_MTIME=$$(stat -f %m .caddy-trusted 2>/dev/null); \
				if [ -n "$$SENTINEL_MTIME" ] && [ "$$VOLUME_CREATED" -gt "$$SENTINEL_MTIME" ]; then \
					echo "Detected Caddy volume recreation - removing trust sentinel"; \
					rm -f .caddy-trusted; \
				fi; \
			fi; \
		fi; \
	fi
endef

# =============================================================================
# Production Deployment Targets
# =============================================================================


docker-build:
	# Build with explicit platform to ensure compatibility with Lightsail
	# Lightsail only supports linux/amd64 containers
	docker build --platform $(PLATFORM) -t $(SVC):$(ARCH_TAG) .

create:
	aws lightsail create-container-service --region $(REGION) --service-name $(SVC) --power $(POWER) --scale $(SCALE)

# Install the patched lightsailctl to fix the "image push response does not contain the image digest" error
install-lightsailctl-fix:
	@echo "Installing patched lightsailctl to fix push issues..."
	@if command -v lightsailctl >/dev/null 2>&1; then \
		echo "Uninstalling existing lightsailctl..."; \
		brew uninstall lightsailctl 2>/dev/null || true; \
	fi
	@echo "Installing Go if needed..."
	@command -v go >/dev/null 2>&1 || brew install go
	@echo "Cloning and building patched lightsailctl..."
	@cd /tmp && rm -rf lightsailctl && \
		git clone https://github.com/paxan/lightsailctl.git -b paxan/image-push-bug-fixes && \
		cd lightsailctl && go install ./...
	@echo "Patched lightsailctl installed successfully!"
	@echo "Version: $$($(HOME)/go/bin/lightsailctl --version)"

push:
	# Use the patched lightsailctl with specified platform image to avoid digest extraction issues
	aws lightsail push-container-image --region $(REGION) --service-name $(SVC) --label web --image $(SVC):$(ARCH_TAG)

deploy:
	@if [ ! -f $(CONTAINERS) ]; then echo "$(CONTAINERS) missing"; exit 1; fi
	aws lightsail create-container-service-deployment \
		--region $(REGION) \
		--service-name $(SVC) \
		--containers file://$(CONTAINERS) \
		--public-endpoint file://deploy/public-endpoint.json \
		--no-cli-pager

update-hosts:
	@echo "Updating ALLOWED_HOSTS to $(SVC).$(HOST_SUFFIX)"
	@sed -i.bak -E 's/"ALLOWED_HOSTS": "[^"]*"/"ALLOWED_HOSTS": "$(SVC).$(HOST_SUFFIX)"/' $(CONTAINERS)
	@echo "Updating CSRF_TRUSTED_ORIGINS to https://$(SVC).$(HOST_SUFFIX)"
	@sed -i.bak -E 's|"CSRF_TRUSTED_ORIGINS": "[^"]*"|"CSRF_TRUSTED_ORIGINS": "https://$(SVC).$(HOST_SUFFIX)"|' $(CONTAINERS)

update-image:
	@echo "Updating containers.json with pushed image..."
	$(eval IMAGE_NAME := $(shell aws lightsail get-container-images --region $(REGION) --service-name $(SVC) --query 'containerImages[0].image' --output text))
	@sed -i.bak 's|"image": ":.*"|"image": "$(IMAGE_NAME)"|' deploy/containers.json
	@echo "Updated image reference to: $(IMAGE_NAME)"

# Pushes container to AWS lightsail
up: docker-build push update-image update-hosts deploy

down:
	aws lightsail delete-container-service --region $(REGION) --service-name $(SVC)
 
sync-env:
	@mkdir -p .cache
	@jq -r '.web.environment | to_entries | map("\(.key)=\(.value)") | .[]' $(CONTAINERS) > .cache/.env
	@echo "PGSSLMODE=require" >> .cache/.env
	# Override DEBUG for local development
	@sed -i '' -e 's/^DEBUG=.*/DEBUG=True/' .cache/.env || true
	@sed -i '' -e 's/^DB_NAME=.*/DB_NAME=local/' .cache/.env || true

# Run containerized local development server
# Runs Docker compose with the local dev environment
# Usage:
#   make local-up                              - Use env generated from containers.json
#   make local-up ENV_FILE=.env.local          - Use custom env file (e.g., for mobile testing)
#   make local-up CONTAINERS=deploy/other.json - Use different containers.json for sync-env
local-up:
	@mkdir -p .cache
	@if [ -n "$(ENV_FILE)" ] && [ -f "$(ENV_FILE)" ]; then \
		cp $(ENV_FILE) .cache/.env; \
		echo "Using environment from $(ENV_FILE)"; \
		echo "Access from your phone at: http://$$(grep ALLOWED_HOSTS $(ENV_FILE) | cut -d= -f2):8000"; \
	elif [ -n "$(ENV_FILE)" ] && [ ! -f "$(ENV_FILE)" ]; then \
		echo "Error: $(ENV_FILE) not found."; \
		echo "Copy .env.local.example to $(ENV_FILE) and fill in all values."; \
		echo ""; \
		echo "To find your IP: ipconfig getifaddr en0"; \
		exit 1; \
	else \
		$(MAKE) sync-env; \
		echo "Using environment generated from containers.json"; \
	fi
	@docker-compose up --build -d

# Help target to document the bug fix
help:
	@echo "WMS Deployment Makefile"
	@echo ""
	@echo "IMPORTANT: This Makefile includes workarounds for lightsailctl bugs:"
	@echo "  - Issue #100: 'image push response does not contain the image digest'"
	@echo "  - Issue #95: 'Unexpected status from PUT request'"
	@echo ""
	@echo "The workarounds include:"
	@echo "  1. Building with explicit --platform $(PLATFORM)"
	@echo "  2. Using patched lightsailctl from PR #102"
	@echo "  3. Automatic PATH configuration for Go binaries"
	@echo ""
	@echo "Configuration variables:"
	@echo "  PLATFORM=$(PLATFORM)     - Docker build platform"
	@echo "  ARCH_TAG=$(ARCH_TAG)     - Image tag suffix"
	@echo "  SVC=$(SVC)               - Service name"
	@echo "  REGION=$(REGION)         - AWS region"
	@echo ""
	@echo "Available targets:"
	@echo "  setup                   - Initial setup (install tools, build, create service)"
	@echo "  setup-deploy            - Complete deployment after URL configuration"
	@echo "  install-lightsailctl-fix - Install patched lightsailctl"
	@echo "  docker-build           - Build Docker image with linux/amd64 platform"
	@echo "  create                 - Create Lightsail container service"
	@echo "  push                   - Push image using patched lightsailctl"
	@echo "  deploy                 - Deploy containers to Lightsail"
	@echo "  up                     - Build, push, and deploy (requires existing service)"
	@echo "  down                   - Delete the container service"
	@echo "  help                   - Show this help message"

# =============================================================================
# Local HTTPS Testing Targets
# =============================================================================

# Run local HTTPS development server with Caddy reverse proxy using mDNS
# Usage:
#   make local-https                                    - Use .env.local.https
#   make local-https ENV_FILE=.env.local.https.custom   - Use custom env file
local-https: ENV_FILE?=.env.local.https
local-https:
	$(call validate-local-https-env,$(ENV_FILE))
	$(call check-local-https-caddy-volumes)
	@mkdir -p .cache
	@cp $(ENV_FILE) .cache/.env
	@# Create root .env for docker-compose variable substitution (ports, domain)
	@cp $(ENV_FILE) .env
	@echo "Using HTTPS environment from $(ENV_FILE)"
	@if [ ! -f .caddy-trusted ]; then \
		echo ""; \
		echo "First-time setup: Installing Caddy root CA..."; \
		$(MAKE) caddy-trust; \
	fi
	@docker-compose up --build -d web caddy
	@echo ""
	@echo "============================================================"
	@echo "Local HTTPS server running!"
	@echo "============================================================"
	@DOMAIN=$$(grep "^DOMAIN=" $(ENV_FILE) | cut -d= -f2); \
	HTTP_PORT=$$(grep "^HTTP_PORT=" $(ENV_FILE) | cut -d= -f2 || echo "8080"); \
	HTTPS_PORT=$$(grep "^HTTPS_PORT=" $(ENV_FILE) | cut -d= -f2 || echo "8443"); \
	echo "Access from desktop OR mobile:"; \
	echo "  http://$$DOMAIN:$$HTTP_PORT (redirects to HTTPS)"; \
	echo "  https://$$DOMAIN:$$HTTPS_PORT (direct HTTPS)"; \
	echo ""; \
	poetry run python deploy/generate_qr.py --url "http://$$DOMAIN:$$HTTP_PORT" --title "Scan to access WMS (desktop or mobile):"; \
	echo ""; \
	echo "For mobile: Install certificate once with 'make caddy-export-ca'"; \
	echo "============================================================"
	@echo ""

# Install Caddy root CA certificate for local HTTPS trust
caddy-trust:
	@echo "Installing Caddy root CA certificate..."
	@docker-compose up -d caddy 2>/dev/null || true
	@sleep 2
	@if ! docker-compose exec caddy caddy trust 2>/dev/null; then \
		echo "Error: Failed to install Caddy CA. Is the caddy container running?"; \
		echo "Try: docker-compose up -d caddy"; \
		exit 1; \
	fi
	@touch .caddy-trusted
	@echo "Caddy CA certificate installed successfully!"
	@echo "You can now access https://<your-hostname>.local:<HTTPS_PORT> without certificate warnings."

# Export Caddy CA certificate and serve it via HTTP for mobile download
# Mobile devices need to install and trust this certificate to connect via HTTPS
# Usage:
#   make caddy-export-ca                                - Use .env.local.https
#   make caddy-export-ca ENV_FILE=.env.local.https.wifi - Use custom env file
caddy-export-ca: ENV_FILE?=.env.local.https
caddy-export-ca:
	$(call validate-local-https-env,$(ENV_FILE))
	@echo "Extracting Caddy root CA certificate..."
	@if ! docker volume inspect wms_caddy_data >/dev/null 2>&1; then \
		echo "Error: wms_caddy_data volume not found. Run 'make local-https' first."; \
		exit 1; \
	fi
	@if ! docker run --rm -v wms_caddy_data:/data alpine cat /data/caddy/pki/authorities/local/root.crt > deploy/caddy-root-ca.crt 2>/dev/null; then \
		echo "Error: Failed to extract CA certificate from Caddy volume."; \
		echo ""; \
		echo "Troubleshooting:"; \
		echo "  1. Ensure Caddy has generated the CA: make local-https"; \
		echo "  2. Check Caddy logs: docker-compose logs caddy"; \
		echo "  3. Verify volume exists: docker volume ls | grep caddy"; \
		echo ""; \
		echo "If the CA path has changed in newer Caddy versions, check:"; \
		echo "  docker run --rm -v wms_caddy_data:/data alpine find /data -name root.crt"; \
		exit 1; \
	fi
	@echo "CA certificate extracted to: deploy/caddy-root-ca.crt"
	@echo ""
	@DOMAIN=$$(grep "^DOMAIN=" $(ENV_FILE) | cut -d= -f2); \
	HTTP_PORT=$$(grep "^HTTP_PORT=" $(ENV_FILE) | cut -d= -f2 || echo "8080"); \
	echo "============================================================"; \
	echo "Starting HTTP server for CA certificate download..."; \
	echo "============================================================"; \
	echo "Download URL: http://$$DOMAIN:8888/caddy-root-ca.crt"; \
	echo ""; \
	echo "Scan this QR code to download the certificate:"; \
	echo ""; \
	poetry run python deploy/generate_qr.py --url "http://$$DOMAIN:8888/caddy-root-ca.crt" --title "Scan to install certificate:"; \
	echo ""; \
	echo "On your mobile device:"; \
	echo "  1. Scan the QR code OR visit: http://$$DOMAIN:8888/caddy-root-ca.crt"; \
	echo "  2. iOS: Settings → Profile Downloaded → Install → Certificate Trust Settings"; \
	echo "  3. Android: Settings → Security → Install from storage"; \
	echo ""; \
	echo "Press Ctrl+C to stop the server after installing"; \
	echo "============================================================"; \
	echo ""; \
	cd deploy && python3 -m http.server 8888

# Stop local HTTPS development server and clean up artifacts
local-https-down:
	@echo "Stopping local HTTPS server..."
	@docker-compose down web caddy
	@echo "Cleaning up HTTPS artifacts..."
	@rm -f .caddy-trusted deploy/caddy-root-ca.crt deploy/caddy-ca-qr.png .env
	@echo "Local HTTPS environment shut down successfully."
	@echo ""
	@echo "Note: Docker volumes (wms_caddy_data, wms_caddy_config) are preserved."
	@echo "To remove volumes completely, run: docker volume rm wms_caddy_data wms_caddy_config"
