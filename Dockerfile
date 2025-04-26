# Use an official Python runtime as a parent image
FROM python:3.11-slim as builder

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Install system dependencies if needed (placeholder)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the project and lock files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv and the lock file
# Use --system to install into the system Python environment
RUN uv pip sync --no-cache --system uv.lock

# Copy the rest of the application code into the container at /app
COPY . .

# Specify the command to run on container start
CMD ["python", "bot.py"]
