#!/bin/bash

# In Poetry 2.0+, the poetry shell command was removed.
# This script restores the convenience of activating the Poetry
# virtual environment directly in your current shell session,
# with a cross-platform command.
# Usage:
#   source config/scripts/common/poetry_shell.sh


ACTIVATE_CMD=$(poetry env activate 2>/dev/null)

# Check if the command retrieval succeeded
if [ $? -ne 0 ]; then
    echo "Error: Failed to retrieve the activation command. Ensure Poetry is installed and configured properly."
    return 1
fi

# Cross-platform handling of the activation command
if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || "$OSTYPE" == "win32" ]]; then
    # Windows: Extract the path and source it directly
    ACTIVATE_PATH=$(echo "$ACTIVATE_CMD" | tr -d "'")
    source "$ACTIVATE_PATH"
else
    # Linux/macOS: Evaluate the activation command
    eval "$ACTIVATE_CMD"
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate the virtual environment."
    return 1
fi
