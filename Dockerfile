# # Dockerfile
# --- 1. use Microsoft’s pre-built image (has Chromium + all libs)
FROM mcr.microsoft.com/playwright/python:v1.51.0-noble

WORKDIR /app

# --- 2. install python deps & agentql
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install agentql

# --- 3. copy code & launch
COPY . .
ENV PORT=8080 PYTHONUNBUFFERED=1
CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080"]