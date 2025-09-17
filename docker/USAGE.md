# Generic Model Runner Docker Image

This directory contains a **generic, reusable** Docker setup that mounts code and resources externally instead of baking them into the image.

## Benefits

- **Reusable**: Same image works for any submission
- **Faster Development**: No rebuild needed for code changes
- **Efficient**: Requirements are cached between runs
- **Flexible**: Easy to test different code versions
- **Smaller Images**: Code and dependencies aren't baked in

## Quick Start

### Using Docker Compose (Recommended)

```bash
# 1. Ensure your directory structure looks like:
# docker/
#   ├── submission/code/
#   │   ├── main.py
#   │   └── requirements.txt
#   └── resources/
#       └── (any resource files)

# 2. Start the service
docker-compose up model-runner
```

### Using Docker Run

```bash
# Build the generic image (amd64 architecture)
docker build --platform linux/amd64 -f docker/Dockerfile.generic -t model-runner:generic .

# Run with volume mounts
docker run -d \
  --name model-runner \
  -p 50051:50051 \
  -v $(pwd)/submission/code:/workspace/submission/code:ro \
  -v $(pwd)/resources:/workspace/resources:ro \
  -v model_runner_cache:/workspace/cache \
  model-runner:generic
```

## Directory Structure

Your project should be organized as follows:

```
your-project/
├── submission/
│   └── code/
│       ├── main.py              # Your model code
│       ├── requirements.txt     # Python dependencies
│       └── (other .py files)
├── resources/                   # Any resource files
│   ├── data.json
│   └── model_weights.pkl
└── docker/
    ├── docker-compose.yml
    └── Dockerfile.generic
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CODE_DIRECTORY` | `/workspace/submission/code` | Path to mounted code |
| `RESOURCE_DIRECTORY` | `/workspace/resources` | Path to mounted resources |
| `REQUIREMENTS_FILE` | `/workspace/submission/code/requirements.txt` | Requirements file path |
| `CACHE_DIRECTORY` | `/workspace/cache` | Cache for installed packages |
| `HAS_GPU` | `false` | GPU availability |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SERVER_ADDRESS` | `[::]:50051` | gRPC server address |

### Override Configuration

```bash
# Using docker-compose
docker-compose run -e LOG_LEVEL=DEBUG model-runner

# Using docker run
docker run -e LOG_LEVEL=DEBUG -e HAS_GPU=true model-runner:generic
```

## Platform Architecture

**Important**: This image is built specifically for **linux/amd64** architecture to ensure consistency across deployment environments. All build commands use `--platform linux/amd64` to guarantee compatibility regardless of the host machine architecture.

## Features

### 1. **Smart Requirements Caching**
- Requirements are only installed when `requirements.txt` changes
- Uses MD5 hash to detect changes
- Cached in persistent volume

### 2. **Flexible Mounting**
- Code directory (read-only recommended)
- Resources directory (read-only or read-write)
- Cache directory (persistent)

### 3. **GPU Support**
```yaml
# In docker-compose.yml
environment:
  - HAS_GPU=true
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

## Development Workflow

### 1. **Initial Setup**
```bash
# Build the generic image once
docker build -f docker/Dockerfile.generic -t model-runner:generic .
```

### 2. **Development Cycle**
```bash
# Edit your code in submission/code/
vim submission/code/main.py

# Restart container (picks up code changes automatically)
docker-compose restart model-runner

# Or just start/stop as needed
docker-compose up model-runner
```

### 3. **Testing Different Versions**
```bash
# Test different code versions by mounting different directories
docker run -v ./v1/code:/workspace/submission/code:ro model-runner:generic
docker run -v ./v2/code:/workspace/submission/code:ro model-runner:generic
```

## Migration from Baked-in Approach

### Old Approach (Dockerfile)
```dockerfile
# Required rebuild for every code change
COPY submission/code/ ./
RUN pip install -r requirements.txt
```

### New Approach (Generic Image)
```bash
# Build once, mount code externally
docker run -v ./code:/workspace/submission/code:ro model-runner:generic
```

### Migration Steps
1. Move your code out of the Docker build context
2. Create `submission/code/` directory structure  
3. Use the generic Dockerfile and docker-compose
4. Mount your code and resources as volumes

## Troubleshooting

### Code Directory Empty
```
ERROR: Code directory is empty or doesn't exist
```
**Solution**: Ensure you're mounting the correct directory with your code files.

### Requirements Installation Failed  
```
ERROR: Could not find a version that satisfies the requirement...
```
**Solution**: Check your `requirements.txt` file and ensure all packages are available.

### Permission Issues
```
Permission denied when accessing mounted files
```
**Solution**: Check file permissions or run with appropriate user mapping:
```bash
docker run --user $(id -u):$(id -g) ...
```

## Advanced Usage

### Multiple Services
Run multiple model-runner instances with different code:

```yaml
services:
  model-runner-v1:
    # ... mount ./v1/code
  model-runner-v2:  
    # ... mount ./v2/code
```

### Custom Entry Point
```bash
# Run shell instead of model-runner
docker run -it --entrypoint /bin/bash model-runner:generic

# Run with custom arguments
docker run model-runner:generic model-runner --help
```