#!/bin/bash

# --- Deploy Telegram Summarizer Bot to Self-Managed Server ---

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
SERVER_IP=${SERVER_IP:-"38.54.75.29"}
CONTAINER_NAME=${CONTAINER_NAME:-"telegram-summarizer"}
IMAGE_NAME=${IMAGE_NAME:-"telegram-summarizer:latest"}
HOST_PORT=${HOST_PORT:-"8080"}
CONTAINER_PORT=${CONTAINER_PORT:-"8080"}

echo "--- Server Deployment Configuration ---"
echo "Server IP:        $SERVER_IP"
echo "Container Name:   $CONTAINER_NAME"
echo "Image Name:       $IMAGE_NAME"
echo "Host Port:        $HOST_PORT"
echo "Container Port:   $CONTAINER_PORT"
echo "----------------------------------------"

# Get the directory of the script itself
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT="$SCRIPT_DIR/.."

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Error: .env file not found in project root. Please create it with your environment variables." >&2
    exit 1
fi

echo "Found .env file. Proceeding with deployment..."

# Stop and remove existing container if it exists
echo "Stopping and removing existing container (if any)..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Remove old image to ensure we build fresh
echo "Removing old image (if any)..."
docker rmi "$IMAGE_NAME" 2>/dev/null || true

# Build the Docker image
echo "Building Docker image '$IMAGE_NAME'..."
cd "$PROJECT_ROOT" || exit 1
docker build -t "$IMAGE_NAME" .
if [ $? -ne 0 ]; then 
    echo "Error: Docker build failed." >&2
    exit 1
fi

# Run the container
echo "Starting container '$CONTAINER_NAME'..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "$HOST_PORT:$CONTAINER_PORT" \
    --env-file .env \
    "$IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "Error: Failed to start container." >&2
    exit 1
fi

echo "Container started successfully!"

# Wait a moment for the container to start
sleep 5

# Check container status
echo "Checking container status..."
docker ps | grep "$CONTAINER_NAME" || {
    echo "Error: Container is not running. Checking logs..."
    docker logs "$CONTAINER_NAME"
    exit 1
}

# Check health endpoint
echo "Checking health endpoint..."
sleep 10  # Give the app time to start
if curl -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
    echo "✅ Health check passed!"
else
    echo "⚠️  Health check failed. Checking logs..."
    docker logs --tail 20 "$CONTAINER_NAME"
fi

# Set Telegram webhook
echo "Setting Telegram webhook..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Source the .env file to get variables
    set -a  # automatically export all variables
    source "$PROJECT_ROOT/.env"
    set +a  # stop automatically exporting
    
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$WEBHOOK_URL" ] && [ -n "$WEBHOOK_SECRET_PATH" ]; then
        FULL_WEBHOOK_URL="${WEBHOOK_URL}${WEBHOOK_SECRET_PATH}"
        echo "Setting webhook to: $FULL_WEBHOOK_URL"
        
        # Prepare JSON payload
        if [ -n "$TELEGRAM_WEBHOOK_SECRET_TOKEN" ]; then
            JSON_PAYLOAD="{\"url\": \"$FULL_WEBHOOK_URL\", \"secret_token\": \"$TELEGRAM_WEBHOOK_SECRET_TOKEN\"}"
        else
            JSON_PAYLOAD="{\"url\": \"$FULL_WEBHOOK_URL\"}"
        fi
        
        # Set webhook
        RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
            -H "Content-Type: application/json" \
            -d "$JSON_PAYLOAD")
        
        if echo "$RESPONSE" | grep -q '"ok":true'; then
            echo "✅ Telegram webhook set successfully!"
        else
            echo "⚠️  Failed to set Telegram webhook. Response: $RESPONSE"
        fi
    else
        echo "⚠️  Missing webhook configuration in .env file. Please set webhook manually."
    fi
fi

echo ""
echo "--- Deployment Complete ---"
echo "Container: $CONTAINER_NAME"
echo "Status: $(docker inspect -f '{{.State.Status}}' $CONTAINER_NAME)"
echo "Logs: docker logs $CONTAINER_NAME"
echo "Stop: docker stop $CONTAINER_NAME"
echo "Restart: docker restart $CONTAINER_NAME"
echo ""
echo "Your bot should now be accessible at: http://$SERVER_IP:$HOST_PORT"
echo "Health check: http://$SERVER_IP:$HOST_PORT/health" 