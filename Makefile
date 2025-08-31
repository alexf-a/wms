SVC?=wms
REGION?=us-west-2
POWER?=nano
SCALE?=1
CONTAINERS?=lightsail/containers.json
# Docker platform architecture - Lightsail only supports linux/amd64
PLATFORM?=linux/amd64
# Image tag suffix based on architecture
ARCH_TAG?=amd64

# lightsailctl bug fix: Ensure the patched version is in PATH
# The official lightsailctl has a bug with "image push response does not contain the image digest"
# We use the patched version from: https://github.com/aws/lightsailctl/pull/102
# Install with: cd /tmp && git clone https://github.com/paxan/lightsailctl.git -b paxan/image-push-bug-fixes && cd lightsailctl && go install ./...
export PATH := $(PATH):$(HOME)/go/bin

.PHONY: docker-build deploy up down create push install-lightsailctl-fix sync-env local-up

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
	@echo "Updating containers.json with pushed image..."
	$(eval IMAGE_NAME := $(shell aws lightsail get-container-images --region $(REGION) --service-name $(SVC) --query 'containerImages[0].image' --output text))
	@sed -i.bak 's|"image": ":.*"|"image": "$(IMAGE_NAME)"|' lightsail/containers.json
	@echo "Updated image reference to: $(IMAGE_NAME)"

deploy:
	@if [ ! -f $(CONTAINERS) ]; then echo "$(CONTAINERS) missing"; exit 1; fi
	aws lightsail create-container-service-deployment \
		--region $(REGION) \
		--service-name $(SVC) \
		--containers file://$(CONTAINERS) \
		--public-endpoint file://lightsail/public-endpoint.json

up: docker-build push deploy

# Complete setup for new environments (installs patched lightsailctl)
setup: install-lightsailctl-fix docker-build create
	@echo ""
	@echo "⚠️  IMPORTANT: Update lightsail/containers.json with the service URL before continuing..."
	@echo "Add the URL from the create command output to ALLOWED_HOSTS in lightsail/containers.json"
	@echo "Then run: make push deploy"
	@echo ""
	@aws lightsail get-container-services --region $(REGION) --query 'containerServices[0].url' --output text

# Complete deployment after URL configuration
setup-deploy: push deploy
	@echo ""
	@echo "🎉 Deployment complete!"
	@aws lightsail get-container-services --region $(REGION) --query 'containerServices[0].{state:state,url:url}' --output table

down:
	aws lightsail delete-container-service --region $(REGION) --service-name $(SVC)
 
sync-env:
	@mkdir -p .cache
	@jq -r '.web.environment | to_entries | map("\(.key)=\(.value)") | .[]' lightsail/containers.json > .cache/.env
	# Override DEBUG for local development
	@sed -i '' -e 's/^DEBUG=.*/DEBUG=True/' .cache/.env || true

local-up: sync-env
	@docker-compose up --build

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
