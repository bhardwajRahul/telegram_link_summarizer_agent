#!/bin/bash

# --- Build and Run the Telegram Summarizer Bot using Docker ---

IMAGE_NAME="telegram-summarizer"
CONTAINER_NAME="summarizer-bot"

# Get the directory of the script itself
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# Go one level up to the project root
PROJECT_ROOT="$SCRIPT_DIR/.."

ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE" >&2
    echo "Please create and configure the .env file before running." >&2
    exit 1
fi

echo "Building the Docker image ($IMAGE_NAME)..."
cd "$PROJECT_ROOT" || exit 1
docker build -t "$IMAGE_NAME" .

if [ $? -ne 0 ]; then
    echo "Error: Docker build failed." >&2
    exit 1
fi

echo "Stopping and removing existing container named '$CONTAINER_NAME' (if any)..."
docker stop "$CONTAINER_NAME" > /dev/null 2>&1
docker rm "$CONTAINER_NAME" > /dev/null 2>&1

echo "Running the Docker container ($CONTAINER_NAME) with .env file..."
echo "Access the health check at http://localhost:8080/health"

docker run -p 8080:8080 --rm --name "$CONTAINER_NAME" --env-file "$ENV_FILE" "$IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "Error: Failed to run Docker container." >&2
    exit 1
fi
