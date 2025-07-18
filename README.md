# Model Runner

Runner used to run real-time models for the CrunchDAO competitions.

# Installation

> [!NOTE]
> **Python 3.11** or later is required.

```
pip install crunch-model-runner
```

# Usage

Once installed, you can run the runner using:

```bash
model-runner --code-directory tests/models_examples/bill
```

> [!NOTE]
> Replace `--code-directory` with the path to the directory containing the code.

## Options

| Declaration                   | Description                                                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `--code-directory <path>`     | The directory path is where the code is located. This directory **must** exist.                                    |
| `--resource-directory <path>` | The directory path to where the resources are located. The directory will be created if it does not exist.         |
| `--main-file <name>`          | The file to use as the entry point to the model. It must be exists in the code directory.                          |
| `--log-level <level>`         | The logging level, must be one of: `"debug"`, `"info"`, `"warning"`, `"error"`, `"critical"`, default to `"info"`. |

# Contribute

Instructions on how to prepare your development environment are available at [CONTRIBUTE.md](./CONTRIBUTE.md).
