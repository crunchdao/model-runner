# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Model Runner is a gRPC-based microservice for remotely executing machine learning models. It provides a standardized interface for loading, initializing, and running inference on ML models through gRPC services.

## Development Commands

### Setup and Dependencies
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Add new dependency
poetry add <package_name>
```

### Running the Server
```bash
# Run with example model
poetry run model-runner --code-directory tests/models_examples/bill

# Alternative method
poetry run python __main__.py --code-directory <model_directory>
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=model_runner

# Run specific test file
poetry run pytest tests/test_specific.py

# Run with verbose output
poetry run pytest -v
```

### Build and Development
```bash
# Generate protobuf code after modifying .proto files
poetry run _generate-proto

# Build and publish package to S3
poetry run _build-publish
```

## Architecture Overview

### Service Layer
The project implements two main gRPC services:

1. **TrainInferStreamService** (`train_infer_servicer.py`): Handles model training and inference operations
   - `Setup`: Initialize model with configuration
   - `Reinitialize`: Reset model state
   - `Train`: Train model with data stream
   - `Infer`: Run inference on data stream

2. **DynamicSubclassService** (`dynamic_subclass_servicer.py`): Enables dynamic class instantiation and method invocation

### Data Type System
The project uses a custom `Variant` type system supporting:
- DOUBLE, INT, STRING for basic types
- PARQUET, ARROW for dataframe formats
- JSON for complex objects
- NONE for null values

Key conversion utilities are in `utils/data_utils.py` and `utils/type_utils.py`.

### Model Integration Pattern
Models must be in a directory containing:
- Python modules with model implementation
- Optional `resources/` directory for model artifacts
- Model classes should implement expected methods (setup, train, infer)

### Protocol Buffers
Three main proto files define the service interface:
- `commons.proto`: Common data types (Variant, DataFrame structures)
- `train_infer.proto`: Training and inference service definitions
- `dynamic_subclass.proto`: Dynamic class service definitions

## Key Implementation Notes

### Error Handling
- All servicer methods include comprehensive error handling with detailed logging
- Errors are properly propagated through gRPC status codes
- See `servicers/train_infer_servicer.py:79-85` for error handling pattern

### Logging
- Centralized logging configuration in `utils/logger.py`
- Log level configurable via `LOG_LEVEL` environment variable
- All modules use consistent logger naming pattern

### Testing Models
When testing model integration:
1. Create model directory under `tests/models_examples/`
2. Include required dependencies in model's `requirements.txt`
3. Ensure model implements expected interface methods
4. Add model-specific requirements installation to GitHub Actions workflow if needed

### Docker Deployment
- Dockerfile in `/docker/` directory
- Supports both CPU and GPU configurations