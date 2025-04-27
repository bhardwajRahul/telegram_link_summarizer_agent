#!/bin/bash

# --- Run the Telegram Summarizer Bot Locally (without Docker) ---

echo "Starting the Telegram Summarizer Bot using uvicorn..."
echo "Ensure you have installed dependencies using 'uv sync'"
echo "Ensure your .env file is configured in the project root."

# Get the directory of the script itself
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# Go one level up to the project root
PROJECT_ROOT="$SCRIPT_DIR/.."

# Run uvicorn from the project root
cd "$PROJECT_ROOT" || exit 1
uvicorn bot:app --host 0.0.0.0 --port 8080 --reload
