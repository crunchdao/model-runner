#!/bin/bash

set -e

echo "Starting Model Runner..."
echo "Code Directory: $CODE_DIRECTORY"
echo "Resource Directory: $RESOURCE_DIRECTORY"
echo "Requirements File: $REQUIREMENTS_FILE"

# Function to install requirements with caching
install_requirements() {
    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "Found requirements.txt, checking if installation needed..."
        
        # Create a hash of requirements.txt for caching
        REQUIREMENTS_HASH=$(md5sum "$REQUIREMENTS_FILE" 2>/dev/null | cut -d' ' -f1 || echo "no-hash")
        CACHE_FILE="$CACHE_DIRECTORY/.requirements_cache_$REQUIREMENTS_HASH"
        
        if [ ! -f "$CACHE_FILE" ]; then
            echo "Installing requirements from $REQUIREMENTS_FILE..."
            pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
            
            # Create cache marker
            mkdir -p "$CACHE_DIRECTORY"
            touch "$CACHE_FILE"
            echo "Requirements installed and cached."
        else
            echo "Requirements already installed (cached)."
        fi
    else
        echo "No requirements.txt found, skipping dependency installation."
    fi
}

# Check if code directory exists and is not empty
if [ ! -d "$CODE_DIRECTORY" ] || [ -z "$(ls -A "$CODE_DIRECTORY" 2>/dev/null)" ]; then
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