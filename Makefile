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

.PHONY: docker-build deploy up down create push install-lightsailctl-fix sync-env local-up update-hosts update-image

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