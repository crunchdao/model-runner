#!/bin/bash

set -e

echo "Starting Model Runner..."
echo "Code Directory: $CODE_DIRECTORY"
echo "Resource Directory: $RESOURCE_DIRECTORY"
echo "Requirements File: $REQUIREMENTS_FILE"

# Function to install requirements 
install_requirements() {
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "Installing requirements from $REQUIREMENTS_FILE..."
        pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
        echo "Requirements installed."
    else
        echo "No requirements.txt found, skipping dependency installation."
    fi
}

# Check if code directory exists and is not empty
if [ ! -d "$CODE_DIRECTORY" ] || [ -z "$(find "$CODE_DIRECTORY" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "ERROR: Code directory is empty or doesn't exist: $CODE_DIRECTORY"
    echo "Please mount your code directory to $CODE_DIRECTORY"
    exit 1
fi

# Check if resource directory exists (create if it doesn't)
if [ ! -d "$RESOURCE_DIRECTORY" ]; then
    echo "Creating resource directory: $RESOURCE_DIRECTORY"
    mkdir -p "$RESOURCE_DIRECTORY"
fi

# Install requirements if needed
install_requirements

# If the first argument is model-runner, pass all arguments to it
if [ "$1" = "model-runner" ]; then
    echo "Starting model-runner service..."
    exec model-runner \
        --code-directory "$CODE_DIRECTORY" \
        --resource-directory "$RESOURCE_DIRECTORY" \
        --address "$SERVER_ADDRESS" \
        --has-gpu "$HAS_GPU" \
        --log-level "$LOG_LEVEL" \
        "${@:2}"  # Pass any additional arguments
else
    # Allow running other commands
    exec "$@"
fi