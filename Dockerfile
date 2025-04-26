# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (placeholder)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt ./

# Install dependencies using pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose the port the app runs on (adjust if your app uses a different port)
# Cloud Run automatically uses the port defined by the PORT env var (default 8080)
EXPOSE 8080

# Specify the command to run on container start using Uvicorn
# Runs the FastAPI app defined as 'app' in the 'bot.py' module
CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080"]
