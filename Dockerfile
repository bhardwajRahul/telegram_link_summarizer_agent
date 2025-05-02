# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install essential system packages (if any are still needed beyond Python)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy the entire application code
COPY . .

# Install dependencies using uv from pyproject.toml
# This avoids using the lock file directly which was causing issues
RUN uv pip install --system .

# Expose the port the app runs on (adjust if your app uses a different port)
# Cloud Run automatically uses the port defined by the PORT env var (default 8080)
EXPOSE 8080

# Specify the command to run on container start using Uvicorn
# Runs the FastAPI app defined as 'app' in the 'bot.py' module
# Use bash -c to allow environment variable substitution for PORT, defaulting to 8080
CMD bash -c 'uvicorn bot:app --host 0.0.0.0 --port ${PORT:-8080}'
