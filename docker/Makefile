# Makefile for Generic Model Runner Docker Image

# Configuration
IMAGE_NAME = crunch-dynamic-model-runner
TAG = latest
FULL_NAME = $(IMAGE_NAME):$(TAG)

# Directories
EXAMPLE_DIR = example
CODE_DIR = $(EXAMPLE_DIR)/submission/code
RESOURCES_DIR = $(EXAMPLE_DIR)/resources

.PHONY: help build run stop clean logs shell test example

help: ## Show this help message
	@echo "Model Runner Generic Docker Image"
	@echo "=================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build the generic Docker image
	@echo "Building generic model-runner image for amd64..."
	docker build --platform linux/amd64 -f Dockerfile.generic -t $(FULL_NAME) ..

run: ## Run the model-runner with example code (requires build first)
	@echo "Running model-runner with example code..."
	docker run -d \
		--name model-runner-example \
		-p 50051:50051 \
		-v $(PWD)/$(CODE_DIR):/workspace/submission/code:ro \
		-v $(PWD)/$(RESOURCES_DIR):/workspace/resources:ro \
		-v model_runner_cache:/workspace/cache \
		$(FULL_NAME)

run-compose: ## Run using docker-compose
	@echo "Starting with docker-compose..."
	docker-compose up -d model-runner

stop: ## Stop running containers
	@echo "Stopping containers..."
	docker stop model-runner-example 2>/dev/null || true
	docker-compose down 2>/dev/null || true

clean: ## Remove containers and images
	@echo "Cleaning up..."
	docker stop model-runner-example 2>/dev/null || true
	docker rm model-runner-example 2>/dev/null || true
	docker-compose down -v 2>/dev/null || true
	docker rmi $(FULL_NAME) 2>/dev/null || true

logs: ## Show logs from running container
	@echo "Showing logs..."
	docker logs -f model-runner-example 2>/dev/null || docker-compose logs -f model-runner

shell: ## Get a shell in the running container
	@echo "Opening shell in container..."
	docker exec -it model-runner-example /bin/bash 2>/dev/null || docker-compose exec model-runner /bin/bash

test: build run ## Build and run a quick test
	@echo "Testing the setup..."
	@sleep 3
	@echo "Checking if server is responding..."
	@docker exec model-runner-example ps aux | grep model-runner || echo "Process check failed"
	@docker logs model-runner-example | tail -10
	@$(MAKE) stop

example: ## Create example submission structure
	@echo "Creating example submission structure..."
	mkdir -p $(CODE_DIR) $(RESOURCES_DIR)
	@echo "Example files already exist in $(EXAMPLE_DIR)/"
	@echo "Directory structure:"
	@tree $(EXAMPLE_DIR) 2>/dev/null || find $(EXAMPLE_DIR) -type f

dev: ## Development mode - build and run with live code mounting
	@echo "Starting development mode..."
	@$(MAKE) build
	@echo "Mounting current directory for live development..."
	docker run -it --rm \
		-p 50051:50051 \
		-v $(PWD)/$(CODE_DIR):/workspace/submission/code \
		-v $(PWD)/$(RESOURCES_DIR):/workspace/resources \
		-v model_runner_cache:/workspace/cache \
		-e LOG_LEVEL=DEBUG \
		$(FULL_NAME)

# Advanced targets

check-health: ## Check if the service is healthy
	@echo "Checking service health..."
	@timeout 10 bash -c 'until nc -z localhost 50051; do sleep 1; done' && echo "Service is responding on port 50051" || echo "Service is not responding"

build-all: ## Build both regular and GPU versions
	@$(MAKE) build
	@echo "Building GPU version for amd64..."
	docker build --platform linux/amd64 -f Dockerfile.generic -t $(IMAGE_NAME):$(TAG)-gpu --build-arg BASE_IMAGE=nvidia/cuda:11.8-runtime-ubuntu20.04 ..

push: ## Push image to registry (set REGISTRY variable first)
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Error: Please set REGISTRY variable (e.g., make push REGISTRY=your-registry.com)"; \
		exit 1; \
	fi
	docker tag $(FULL_NAME) $(REGISTRY)/$(FULL_NAME)
	docker push $(REGISTRY)/$(FULL_NAME)

build-push: ## Build and push image in one step (amd64 only)
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Error: Please set REGISTRY variable (e.g., make build-push REGISTRY=your-registry.com)"; \
		exit 1; \
	fi
	@echo "Building and pushing amd64 image to $(REGISTRY)/$(FULL_NAME)..."
	docker buildx build --platform linux/amd64 -f Dockerfile.generic -t $(REGISTRY)/$(FULL_NAME) --push ..

# Usage examples
usage: ## Show usage examples
	@echo "Usage Examples:"
	@echo "==============="
	@echo ""
	@echo "1. Quick start:"
	@echo "   make build run"
	@echo ""
	@echo "2. Development mode:"
	@echo "   make dev"
	@echo ""
	@echo "3. Using docker-compose:"
	@echo "   make run-compose"
	@echo ""
	@echo "4. Check logs:"
	@echo "   make logs"
	@echo ""
	@echo "5. Get a shell:"
	@echo "   make shell"