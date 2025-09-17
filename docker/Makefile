# Makefile for Generic Model Runner Docker Image

# Configuration
IMAGE_NAME = crunch-dynamic-model-runner
VERSION ?= 0.5.0
TAG = latest
FULL_NAME = $(IMAGE_NAME):$(TAG)
VERSIONED_NAME = $(IMAGE_NAME):$(VERSION)

# Directories
EXAMPLE_DIR = example
CODE_DIR = $(EXAMPLE_DIR)/submission/code
RESOURCES_DIR = $(EXAMPLE_DIR)/resources

build: ## Build the generic Docker image with version and latest tags
	@echo "Building generic model-runner image for amd64..."
	@echo "Version: $(VERSION)"
	docker build --platform linux/amd64 -f Dockerfile.generic -t $(VERSIONED_NAME) -t $(FULL_NAME) ..

push: ## Push both versioned and latest images to registry
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Error: Please set REGISTRY variable (e.g., make push REGISTRY=your-registry.com)"; \
		exit 1; \
	fi
	@echo "Pushing version $(VERSION) and latest tags..."
	docker tag $(VERSIONED_NAME) $(REGISTRY)/$(VERSIONED_NAME)
	docker tag $(FULL_NAME) $(REGISTRY)/$(FULL_NAME)
	docker push $(REGISTRY)/$(VERSIONED_NAME)
	docker push $(REGISTRY)/$(FULL_NAME)

run-example: ## Show example docker run command for custom code
	@echo "Example docker run commands:"
	@echo "============================"
	@echo ""
	@echo "# Run with your own code (basic):"
	@echo "docker run -d \\"
	@echo "  --name my-model-runner \\"
	@echo "  -p 50051:50051 \\"
	@echo "  -v /path/to/your/code:/workspace/submission/code:ro \\"
	@echo "  -v /path/to/your/resources:/workspace/resources:ro \\"
	@echo "  -v model_runner_cache:/workspace/cache \\"
	@echo "  $(VERSIONED_NAME)"
	@echo ""
	@echo "# Run with environment variables and latest tag:"
	@echo "docker run -d \\"
	@echo "  --name my-model-runner \\"
	@echo "  -p 50051:50051 \\"
	@echo "  -v /path/to/your/code:/workspace/submission/code:ro \\"
	@echo "  -v /path/to/your/resources:/workspace/resources:ro \\"
	@echo "  -v model_runner_cache:/workspace/cache \\"
	@echo "  -e LOG_LEVEL=DEBUG \\"
	@echo "  -e HAS_GPU=false \\"
	@echo "  $(FULL_NAME)"
	@echo ""
	@echo "# Interactive run (for debugging):"
	@echo "docker run -it --rm \\"
	@echo "  -p 50051:50051 \\"
	@echo "  -v /path/to/your/code:/workspace/submission/code \\"
	@echo "  -v /path/to/your/resources:/workspace/resources \\"
	@echo "  $(VERSIONED_NAME) /bin/bash"
	@echo ""
	@echo "Current version: $(VERSION)"