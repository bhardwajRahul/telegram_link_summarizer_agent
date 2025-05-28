# Telegram Link Summarizer Agent

[Join the Telegram Channel @tech_links for curated tech news and interesting links](https://t.me/tech_links)

 [![GitHub Repo stars](https://img.shields.io/github/stars/kargarisaac/telegram_link_summarizer_agent)](https://github.com/kargarisaac/telegram_link_summarizer_agent)
 [![GitHub forks](https://img.shields.io/github/forks/kargarisaac/telegram_link_summarizer_agent)](https://github.com/kargarisaac/telegram_link_summarizer_agent)
 [![GitHub License](https://img.shields.io/github/license/kargarisaac/telegram_link_summarizer_agent)](https://github.com/kargarisaac/telegram_link_summarizer_agent)
 [![Telegram Channel](https://img.shields.io/badge/Telegram-Join%20Channel-blue?logo=telegram)](https://t.me/tech_links)
 [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/kargarisaac/telegram_link_summarizer_agent)

If you want to get the latest news and interesting links for free, feel free to join the channel. If you find this project useful, giving the repository a star would be appreciated.

![Agent Visualization](./images/image.png)

![System Diagram](./images/system_arch.jpg)


An agentic Telegram bot designed to summarize web links (articles, papers, tweets etc.) sent in a chat. It uses LangGraph to orchestrate multiple tools and language models to determine the link type, extract content, and generate concise summaries.

## ✨ Features

*   **Link Summarization:** Extracts content from URLs (webpages, PDFs, Twitter/X, LinkedIn posts) and provides summaries.
*   **Robust YouTube Support:** Handles YouTube links using Playwright and AgentQL to extract video title and description.
*   **LLM Routing:** Uses a BAML LLM function (`RouteRequest`) to determine the type of link (Webpage, PDF, Twitter, LinkedIn, Unsupported).
*   **Web Search/Extraction:** Uses Tavily for standard webpage content extraction.
*   **PDF Support:** Can process and summarize PDF documents found at URLs.
*   **Twitter/X Support:** Fetches tweet content (including threads) using the `twitterapi.io` service.
*   **LinkedIn Support:** Extracts content from LinkedIn post URLs using Playwright and AgentQL.
*   **Agentic Workflow:** Leverages LangGraph for a multi-step reasoning process.
*   **BAML Integration:** Uses BAML for structured output generation (summaries and routing).
*   **Telegram Bot Interface:** Interacts via a simple Telegram bot, replying silently on failure.

## 🛠️ Tech Stack

*   **Routing/Summarization:** BAML (Boundary) + LLM (e.g., Gemini, Deepseek)
*   **Orchestration:** LangGraph
*   **YouTube Extraction:** `playwright`, `agentql`
*   **Twitter/X API:** `twitterapi.io` via `requests`
*   **Web Extraction:** Tavily Search SDK
*   **LinkedIn Extraction:** `playwright`, `agentql`
*   **PDF Extraction:** PyMuPDF (`fitz`)
*   **Telegram Bot:** `python-telegram-bot`
*   **Web Framework:** FastAPI + Uvicorn
*   **Dependencies:** Managed via `pyproject.toml` (using `uv` or `pip`)

## 🚀 Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd telegram_link_summarizer_agent
    ```

2.  **Install Dependencies (using [`uv`](https://github.com/astral-sh/uv) or `pip`))**
    *   You can use [`uv`](https://github.com/astral-sh/uv) or standard `pip`:
        ```bash
        # Using uv (recommended)
        uv pip install -e . # Install in editable mode

        # Or using pip
        pip install -e . # Install in editable mode
        ```
    *   Install Playwright browsers:
        ```bash
        playwright install
        ```

3.  **Set up Environment Variables:**
    Create a file named `.env` in the project root directory. Add the following environment variables with your actual values:
    ```env
    # --- Core API Keys ---
    # Select *one* LLM provider for BAML functions (or configure multi-provider
    # GEMINI_API_KEY="your_google_gemini_api_key" # For Google LLMs
    DEEPSEEK_API_KEY="your_deepseek_api_key" # For Deepseek LLMs
    GOOGLE_API_KEY="your_google_cloud_api_key" # e.g., For Google LLMs or other Google Cloud services

    # Tools
    TAVILY_API_KEY="your_tavily_api_key"
    TWITTER_API_IO_KEY="your_twitterapi.io_api_key" # API Key for twitterapi.io service
    AGENTQL_API_KEY="your_agentql_api_key" # API Key for AgentQL

    # --- Telegram Bot Configuration ---
    TELEGRAM_BOT_TOKEN="your_telegram_bot_token"

    # --- Webhook Configuration (Needed for deployment or local testing with ngrok) ---
    # For ngrok, use the https://<your-ngrok-subdomain>.ngrok-free.app URL
    # For deployment, this isn't strictly needed in the .env for the *deployed* app,
    # but the deployment script will set the webhook based on the Cloud Run URL.
    # WEBHOOK_URL="your_webhook_url_or_ngrok_url"

    # Secure your webhook (generate strong random strings for these)
    TELEGRAM_WEBHOOK_SECRET_TOKEN="your_strong_random_secret_token"
    # Example: /webhook/aBcDeF12345 - must start with a slash!
    # WEBHOOK_SECRET_PATH="/your_unique_and_random_webhook_path"

    # --- Polling vs Webhook Mode (for bot.py) ---
    # Set USE_POLLING to "true" to run the bot in polling mode (recommended for self-managed servers without HTTPS).
    # If USE_POLLING is "true", WEBHOOK_URL and related settings are ignored by bot.py.
    # Defaults to webhook mode if not set or "false".
    # USE_POLLING="true" 

    # --- Webhook Configuration (Only if NOT using USE_POLLING="true") ---
    # For local ngrok testing:
    # WEBHOOK_URL="https://your-ngrok-subdomain.ngrok-free.app"
    # WEBHOOK_SECRET_PATH="your_unique_and_random_webhook_path" # e.g., webhook_abc123 (no leading slash for bot.py)
    
    # For self-managed server with public IP (HTTP, for testing - Telegram prefers HTTPS for production):
    # WEBHOOK_URL="http://YOUR_SERVER_IP:8080"
    # WEBHOOK_SECRET_PATH="your_unique_and_random_webhook_path" # e.g., webhook_abc123 (no leading slash for bot.py)

    # For self-managed server with domain and HTTPS (Production Webhook):
    # WEBHOOK_URL="https://yourbot.yourdomain.com" # Nginx would proxy to http://localhost:8080
    # WEBHOOK_SECRET_PATH="your_unique_and_random_webhook_path" # e.g., webhook_abc123 (no leading slash for bot.py)
    
    # For Google Cloud Run (this is typically set by the deploy_cloud_run.sh script, not manually in .env):
    # WEBHOOK_URL="your_cloud_run_service_url" 
    # WEBHOOK_SECRET_PATH="your_unique_and_random_webhook_path" # e.g., webhook_abc123 (no leading slash for bot.py)

    # Secure your webhook (generate strong random strings for these) - ALWAYS NEEDED FOR WEBHOOK MODE
    # TELEGRAM_WEBHOOK_SECRET_TOKEN="your_strong_random_secret_token"
    ```
    **Important:** 
    *   Get your `TWITTER_API_IO_KEY` from [twitterapi.io](https://twitterapi.io/).
    *   Ensure your chosen LLM API Key (`GEMINI_API_KEY` or `DEEPSEEK_API_KEY`) is uncommented and valid.
    *   Keep your `.env` file secure and do not commit it. The `.gitignore` should exclude `.env`.

## ▶️ Usage

1.  **(Optional) Run the Agent Script Directly (for testing specific URLs):**
    *   You can test the core agent logic by running `agent.py`. Modify the test cases at the bottom of the script.
    ```bash
    python agent.py
    ```

## 📊 Agent Visualization

The `agent_viz.py` script can be used to generate a visualization of the LangGraph agent (like the image at the top). Ensure `graphviz` is installed (`brew install graphviz` or `sudo apt-get install graphviz`).

```bash
python agent_viz.py
```
This will generate an `agent_graph.png` file.

## Local Running (Webhook Mode)

This runs the FastAPI server using `uvicorn`. This requires `USE_POLLING="false"` and a publicly accessible `WEBHOOK_URL` set in your `.env` file (e.g., using ngrok) for the bot to receive messages from Telegram.

Make sure you have installed dependencies (`uv pip install -e .`) and configured your `.env` file.

```bash
# Make the script executable (only needed once)
chmod +x ./scripts/run_local.sh

# Run the local server
./scripts/run_local.sh
```

You can check if the server is running by accessing the health check endpoint: `curl http://localhost:8080/health`

## Testing Webhooks Locally with ngrok

When running your bot locally, Telegram cannot reach your computer directly because `localhost` is not accessible from the public internet. To test real Telegram messages with webhooks during development, you can use [ngrok](https://ngrok.com/) to create a secure tunnel from a public URL to your local machine.

### Steps

1.  **Install ngrok:**
   - Download from https://ngrok.com/download or install via your package manager.
   - On macOS (Homebrew):
     ```bash
     brew install ngrok
     ```
   - On Linux:
     ```bash
     sudo snap install ngrok
     ```
   - On Windows: Download and extract the executable from the website.

2.  **Start your local server:**
   ```bash
   # Ensure the script is executable
   chmod +x ./scripts/run_local.sh
   # Run the local server
   ./scripts/run_local.sh
   ```

3.  **Start ngrok to expose port 8080:**
   ```bash
   ngrok http 8080
   ```
   - You will see output like:
     ```
     Forwarding https://abcd-1234.ngrok-free.app -> http://localhost:8080
     ```
   - Copy the HTTPS URL provided by ngrok (e.g., `https://abcd-1234.ngrok-free.app`).

4.  **Update your `.env` file:**
   - Set the `WEBHOOK_URL` to the ngrok HTTPS URL:
     ```env
     WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app
     ```
   - Save the file.

5.  **Restart your local server:**
   - Stop the running `./scripts/run_local.sh` process (Ctrl+C) and start it again:
     ```bash
     ./scripts/run_local.sh
     ```
   - On startup, the bot should attempt to register the webhook with Telegram using your public ngrok URL (if `bot.py` is configured to do so based on `WEBHOOK_URL`).

6.  **Test your bot:**
   - Send a message with a link to your Telegram bot as usual.
   - Telegram will send the update to your ngrok public URL, which forwards it to your local server.
   - You should see logs in your terminal and receive a response from your local bot.

**Tip:** If you restart ngrok, you will get a new public URL. Update your `.env` and restart the server each time.

**Security Note:** For production, always use a secret path (`WEBHOOK_SECRET_PATH`) and a secret token (`TELEGRAM_WEBHOOK_SECRET_TOKEN`) for your webhook endpoint. For local ngrok testing, ensure these variables are also set in your `.env` if your `bot.py` requires them even locally.

## Docker Testing

This builds the Docker image and runs the container locally. Ensure your `.env` file is present and configured in the project root.

```bash
# Make the script executable (only needed once)
chmod +x ./scripts/run_docker.sh

# Build and run the Docker container
./scripts/run_docker.sh
```

You can check the health endpoint at `http://localhost:8080/health`

### Testing Docker Locally with ngrok

You can also test the Docker container with ngrok to receive real Telegram messages:

1.  **Run the Docker Container:**
    ```bash
    # Ensure script is executable
    chmod +x ./scripts/run_docker.sh
    # Build and run the container (loads .env)
    ./scripts/run_docker.sh 
    ```
    *(Leave this terminal running)*

2.  **Start ngrok:** In a *new* terminal, run:
    ```bash
    ngrok http 8080 
    ```
    Copy the HTTPS URL provided by ngrok.

3.  **Update `.env`:** Set the `WEBHOOK_URL` variable in your `.env` file to the ngrok HTTPS URL.

4.  **Restart Docker Container:** Stop the running container (Ctrl+C in the first terminal, or `docker stop summarizer-bot`) and restart it using:
    ```bash
    ./scripts/run_docker.sh
    ```
    This ensures the container picks up the new `WEBHOOK_URL` from the `.env` file.

5.  **Test:** Send messages to your bot. They should be routed through ngrok to your running Docker container.

## Deploying to a Self-Managed Server/VM (Docker)

This method uses Docker and the provided `scripts/deploy_server.sh` script to deploy the bot to your own virtual machine or dedicated server. This is the recommended approach for self-hosting.

### 1. Server Preparation

SSH into your server and ensure `git` and `docker` are installed.

```bash
# Update system (example for Debian/Ubuntu)
sudo apt update && sudo apt upgrade -y

# Install Git
sudo apt install -y git

# Install Docker
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Optional: Add your user to the docker group to run docker commands without sudo
# sudo usermod -aG docker $USER
# newgrp docker # Or log out and log back in
```

### 2. Clone Repository

Clone your repository onto the server:
```bash
git clone <your-repo-url>
cd telegram_link_summarizer_agent
```

### 3. Configure Environment (`.env` file)

Create a `.env` file in the project root on your server.

**Option A: Polling Mode (Recommended for Simplicity)**
This is the easiest way to get started on a self-managed server as it doesn't require a public domain, SSL, or complex firewall/proxy setup beyond allowing outbound connections.

```env
# In your .env file on the server:
USE_POLLING="true"

# --- Core API Keys ---
DEEPSEEK_API_KEY="your_deepseek_api_key"
# GEMINI_API_KEY="your_google_gemini_api_key"
TAVILY_API_KEY="your_tavily_api_key"
TWITTER_API_IO_KEY="your_twitterapi.io_api_key"
AGENTQL_API_KEY="your_agentql_api_key"

# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"

# --- Webhook related variables can be omitted or commented out when USE_POLLING="true" ---
# WEBHOOK_URL=
# WEBHOOK_SECRET_PATH=
# TELEGRAM_WEBHOOK_SECRET_TOKEN=
```

**Option B: Webhook Mode**
If you prefer webhook mode, you'll need a way for Telegram to reach your bot.

*   **Using Server IP (HTTP - for testing only, Telegram prefers HTTPS):**
    ```env
    # .env on server
    USE_POLLING="false" # Or omit
    WEBHOOK_URL="http://YOUR_SERVER_PUBLIC_IP:8080"
    WEBHOOK_SECRET_PATH="your_random_webhook_path_string" # e.g., webhook_bot123 (NO leading slash here)
    TELEGRAM_WEBHOOK_SECRET_TOKEN="your_strong_random_token"
    # ... other API keys ...
    ```
    You'll also need to ensure your server's firewall allows inbound traffic on port `8080`.
    ```bash
    sudo ufw allow 8080/tcp
    ```

*   **Using a Domain Name (HTTPS - Recommended for Production Webhooks):**
    This involves setting up a domain name pointing to your server, using a reverse proxy like Nginx, and obtaining an SSL certificate (e.g., with Let's Encrypt).
    ```env
    # .env on server
    USE_POLLING="false" # Or omit
    WEBHOOK_URL="https://yourbot.yourdomain.com" # Nginx will handle HTTPS and proxy to the bot
    WEBHOOK_SECRET_PATH="your_random_webhook_path_string"
    TELEGRAM_WEBHOOK_SECRET_TOKEN="your_strong_random_token"
    # ... other API keys ...
    ```
    Your Nginx would be configured to listen on port 443 (HTTPS), terminate SSL, and proxy requests for your `WEBHOOK_SECRET_PATH` to `http://localhost:8080`. Firewall should allow port 443.

### 4. Run Deployment Script

The `deploy_server.sh` script will build the Docker image and start the container.
```bash
chmod +x ./scripts/deploy_server.sh
./scripts/deploy_server.sh
```
The script uses port `8080` by default.

### 5. Monitoring

*   **View logs:** `docker logs -f telegram-summarizer`
*   **Check status:** `docker ps`
*   **Stop:** `docker stop telegram-summarizer`
*   **Start:** `docker start telegram-summarizer`
*   **Restart:** `docker restart telegram-summarizer`

If using polling mode, the bot should start processing messages. If using webhook mode, ensure your webhook is correctly set with Telegram (the `deploy_server.sh` script attempts this if it finds webhook variables in `.env`, but `bot.py` also tries on startup).

## Deploying to Google Cloud Run

This guide assumes you have a GCP account, `gcloud` CLI installed and configured, and Docker installed.

The deployment process involves:
1.  **Setting up Secrets:** Securely store your API keys and tokens in Google Cloud Secret Manager.
2.  **Building & Pushing Image:** Build the Docker image and push it to Google Artifact Registry.
3.  **Deploying Service:** Deploy the image to Cloud Run, mapping the secrets to environment variables.
4.  **Setting Webhook:** Configure the Telegram webhook to point to your Cloud Run service URL.

We have provided scripts to streamline this process.

### 1. Setup Secrets

This script helps you create secrets in Google Cloud Secret Manager and add your sensitive values (API keys, tokens).

**IMPORTANT:** Before running, you **must** edit the `SECRETS` array inside `scripts/setup_secrets.sh` to include the *exact names* of the environment variables defined in your `.env` file (e.g., `TELEGRAM_BOT_TOKEN`, `TAVILY_API_KEY`, `TWITTER_API_IO_KEY`, `GEMINI_API_KEY` etc.).

```bash
# Make the script executable (only needed once)
chmod +x ./scripts/setup_secrets.sh

# Run the secret setup script (it will prompt for project ID and secret values)
./scripts/setup_secrets.sh
```

Follow the prompts to enter your GCP Project ID (if not already configured) and the values for each secret.

### 2. Deploy to Cloud Run

This script automates building the image, pushing it to Artifact Registry, deploying to Cloud Run, and setting the Telegram webhook.

**IMPORTANT:** Before running, you **must** edit the `SECRETS_TO_MAP` array inside `scripts/deploy_cloud_run.sh`. This array defines how the secrets you created map to environment variables in your Cloud Run service. Ensure the secret names match those used in `setup_secrets.sh` (e.g., `TWITTER_API_IO_KEY=twitter-api-io-key-secret-name:latest`).

```bash
# Make the script executable (only needed once)
chmod +x ./scripts/deploy_cloud_run.sh

# Run the deployment script (it will prompt for configuration)
./scripts/deploy_cloud_run.sh
```

The script will prompt you for your GCP Project ID, Region, Service Name, and Artifact Registry Repository Name if they are not set as environment variables. It will then guide you through the build, push, and deployment process, including setting the Telegram webhook automatically if it can find your `TELEGRAM_BOT_TOKEN` secret mapping.

### Manual Steps (If needed)

<details>
<summary>Click to view manual gcloud commands</summary>

1.  **Set Environment Variables (Shell):**
    ```bash
    export PROJECT_ID="your-gcp-project-id"
    export REGION="your-preferred-region" # e.g., us-central1
    export SERVICE_NAME="telegram-summarizer"
    export REPO_NAME="my-summarizer-bot-repo" # Or your preferred Artifact Registry repo name
    export IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

    gcloud config set project $PROJECT_ID
    gcloud config set run/region $REGION
    ```
2.  **Enable Required APIs:**
    ```bash
    gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
    ```
3.  **Create Artifact Registry Repository (if needed):**
    ```bash
    gcloud artifacts repositories create $REPO_NAME \
      --repository-format=docker \
      --location=$REGION \
      --description="Docker repository for bots"
    ```
4.  **Configure Docker Authentication:**
    ```bash
    gcloud auth configure-docker ${REGION}-docker.pkg.dev
    ```5.  **Manage Secrets with Secret Manager (Recommended):**
    Store API keys and tokens securely using Google Cloud Secret Manager. Use the `gcloud` CLI (as done by `setup_secrets.sh`):

    *   **Create Secret:** (Example: `twitter-api-io-key` for the twitterapi.io key)
        ```bash
        gcloud secrets create twitter-api-io-key --replication-policy="automatic"
        # Add others like tavily-api-key, telegram-bot-token, gemini-api-key, etc.
        ```

    *   **Add Secret Version:**
        ```bash
        printf "YOUR_ACTUAL_TWITTERAPI_IO_KEY" | gcloud secrets versions add twitter-api-io-key --data-file=-
        # Add versions for other secrets...
        ```

6.  **Build and Push Docker Image:**
    ```bash
    # Build
    docker build -t $IMAGE_NAME .
    # Push
    docker push $IMAGE_NAME
    ```

7.  **Deploy to Cloud Run:**
    Replace `SECRET_NAME=SECRET_ID:latest,...` with your actual secret mappings, including `TWITTER_API_IO_KEY`.
    ```bash
    gcloud run deploy $SERVICE_NAME \
      --image $IMAGE_NAME \
      --platform managed \
      --region $REGION \
      --port 8080 \
      --allow-unauthenticated \
      --set-secrets=TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TAVILY_API_KEY=tavily-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest,TWITTER_API_IO_KEY=twitter-api-io-key:latest,TELEGRAM_WEBHOOK_SECRET_TOKEN=webhook-secret-token:latest
      # Adjust secret names (e.g., twitter-api-io-key, webhook-secret-token) and versions as needed
    ```

8.  **Get Service URL & Set Telegram Webhook:**
    ```bash
    # Get the URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
    echo "Service URL: $SERVICE_URL"

    # Get your bot token (replace secret-id if different)
    TELEGRAM_BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
    # Get your webhook secret (optional, replace secret-id if different)
    WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=telegram-webhook-secret-token)

    # Get your webhook path (replace secret-id if different)
    WEBHOOK_SECRET_PATH_VAL=$(gcloud secrets versions access latest --secret=webhook-secret-path) # Assuming you stored it
    # Get your webhook secret token (replace secret-id if different)
    WEBHOOK_SECRET_TOKEN_VAL=$(gcloud secrets versions access latest --secret=webhook-secret-token) 

    curl -F "url=${SERVICE_URL}${WEBHOOK_SECRET_PATH_VAL}" \
         -F "secret_token=${WEBHOOK_SECRET_TOKEN_VAL}" \
         https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook
    ```

</details>

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

---

**Stay updated:** [Join the Telegram Channel @tech_links](https://t.me/tech_links) for the latest news and interesting links. If you find this project useful, please consider starring the repository.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kargarisaac/telegram_link_summarizer_agent&type=Date)](https://www.star-history.com/#kargarisaac/telegram_link_summarizer_agent&Date)