# Getting Started

To get started with this project, follow the steps below:

## Prerequisites

Make sure you have the following installed:

- **Python 3.11**, or later
- **Poetry**, a package manager ([install](https://python-poetry.org/docs/))

## Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <project_folder>
   ```

2. Use Poetry to install the dependencies:
   ```bash
   poetry install
   ```

3. Activate the Poetry virtual environment:
   ```bash
   poetry shell
   ```

# Protocol Buffers

This project uses [gRPC](https://grpc.io/) for communication. You can generate the necessary gRPC code if you change the `[model_runner.proto](model_runner/protos/model_runner.proto)` file by using the following command:

```bash
poetry run _generate-proto
```

Ensure all `.proto` files are present in the appropriate directory before running the above command.

# Testing

To run the tests for this project, execute:
Make sure the gRPC server is correctly set up and running before running the tests. (Next version of tests will introduce this automatically)

```bash
poetry run pytest
```

# Publishing 

Currently, code delivery is done through a build and push to S3, where the orchestrator retrieves it to build a Docker image  (to improve in the futur)
```bash
poetry run _build-publish
```
