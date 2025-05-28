# # Dockerfile
# --- 1. use Microsoft's pre-built image (has Chromium + all libs)
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# --- 2. install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# --- 3. copy dependency files
COPY pyproject.toml uv.lock ./

# --- 4. install dependencies using uv
RUN uv sync --frozen --no-cache

# --- 5. copy code & launch
COPY . .
ENV PORT=8080 PYTHONUNBUFFERED=1
CMD ["uv", "run", "uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080"]