# Makefile for Generic Model Runner Docker Image

# Configuration
IMAGE_NAME = crunch-dynamic-model-runner
VERSION ?= 0.5.0
TAG = latest
FULL_NAME = $(IMAGE_NAME):$(TAG)
VERSIONED_NAME = $(IMAGE_NAME):$(VERSION)

# AWS ECR Configuration
AWS_ACCOUNT_ID = 728958649654
AWS_REGION = eu-west-1
ECR_REGISTRY = $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
ECR_REPOSITORY = $(ECR_REGISTRY)/$(IMAGE_NAME)
ECR_VERSIONED_NAME = $(ECR_REPOSITORY):$(VERSION)
ECR_LATEST_NAME = $(ECR_REPOSITORY):$(TAG)

# Directories
EXAMPLE_DIR = example
CODE_DIR = $(EXAMPLE_DIR)/submission/code
RESOURCES_DIR = $(EXAMPLE_DIR)/resources

build: ## Build the generic Docker image with version and latest tags
	@echo "Building generic model-runner image for amd64..."
	@echo "Version: $(VERSION)"
	docker build --platform linux/amd64 -f Dockerfile.generic -t $(VERSIONED_NAME) -t $(FULL_NAME) ..

ecr-login: ## Login to AWS ECR
	@echo "Logging into AWS ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)

push: ## Push both versioned and latest images to AWS ECR
	@echo "Pushing version $(VERSION) and latest tags to ECR..."
	docker tag $(VERSIONED_NAME) $(ECR_VERSIONED_NAME)
	docker tag $(FULL_NAME) $(ECR_LATEST_NAME)
	docker push $(ECR_VERSIONED_NAME)
	docker push $(ECR_LATEST_NAME)

push-with-login: ## Login to ECR and push images
	@$(MAKE) ecr-login
	@$(MAKE) push

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
	@echo ""
	@echo "# Run from ECR:"
	@echo "docker run -d \\"
	@echo "  --name my-model-runner-ecr \\"
	@echo "  -p 50051:50051 \\"
	@echo "  -v /path/to/your/code:/workspace/submission/code:ro \\"
	@echo "  -v /path/to/your/resources:/workspace/resources:ro \\"
	@echo "  -v model_runner_cache:/workspace/cache \\"
	@echo "  $(ECR_VERSIONED_NAME)"

build-push: ## Build and push both versioned and latest images to ECR in one step
	@echo "Building and pushing amd64 image version $(VERSION) and latest to ECR..."
	@$(MAKE) ecr-login
	docker buildx build --platform linux/amd64 -f Dockerfile.generic \
		-t $(ECR_VERSIONED_NAME) \
		-t $(ECR_LATEST_NAME) \
		--push ..

version: ## Show current version and ECR details
	@echo "Current version: $(VERSION)"
	@echo "Local images:"
	@echo "  Versioned: $(VERSIONED_NAME)"
	@echo "  Latest: $(FULL_NAME)"
	@echo "ECR images:"
	@echo "  Versioned: $(ECR_VERSIONED_NAME)"
	@echo "  Latest: $(ECR_LATEST_NAME)"
	@echo "ECR Registry: $(ECR_REGISTRY)"

ecr-pull: ## Pull images from ECR
	@echo "Pulling images from ECR..."
	@$(MAKE) ecr-login
	docker pull $(ECR_VERSIONED_NAME)
	docker pull $(ECR_LATEST_NAME)

ecr-info: ## Show ECR repository information
	@echo "ECR Repository Information:"
	@echo "=========================="
	@echo "Account ID: $(AWS_ACCOUNT_ID)"
	@echo "Region: $(AWS_REGION)" 
	@echo "Registry: $(ECR_REGISTRY)"
	@echo "Repository: $(ECR_REPOSITORY)"
	@echo ""
	@echo "Images:"
	@echo "  $(ECR_VERSIONED_NAME)"
	@echo "  $(ECR_LATEST_NAME)"
	@echo ""
	@echo "AWS Console URL:"
	@echo "  https://$(AWS_REGION).console.aws.amazon.com/ecr/repositories/private/$(AWS_ACCOUNT_ID)/$(IMAGE_NAME)?region=$(AWS_REGION)"