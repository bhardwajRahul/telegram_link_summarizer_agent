# Telegram Link Summarizer Agent

![Agent Visualization](./images/image.png)

An agentic Telegram bot designed to summarize web links (articles, papers, etc.) sent in a chat. It uses LangGraph to orchestrate multiple tools and language models to extract content, search for relevant information, and generate concise summaries.

## ✨ Features

*   **Link Summarization:** Extracts content from URLs and provides summaries.
*   **Web Search Integration:** Uses Tavily Search to gather context if needed.
*   **PDF Support:** Can process and summarize PDF documents found at URLs.
*   **Agentic Workflow:** Leverages LangGraph for a multi-step reasoning process.
*   **BAML Integration:** Uses BAML for structured output generation.
*   **Telegram Bot Interface:** Interacts via a simple Telegram bot.

## 🛠️ Tech Stack

*   **Orchestration:** LangGraph
*   **LLM Interaction/Structured Output:** BAML (Boundary)
*   **Telegram Bot:** `python-telegram-bot`
*   **Web Scraping:** Firecrawl, Beautiful Soup, Pyppeteer
*   **Search:** Tavily Search
*   **Language Models:** Configurable (defaults likely via LangChain/OpenAI)
*   **Dependencies:** Managed via `pyproject.toml` (using `uv` or `pip`)

## 🚀 Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd telegram_link_summarizer_agent
    ```

2.  **Install Dependencies (using [`uv`](https://github.com/astral-sh/uv))**
    *   You can use [`uv`](https://github.com/astral-sh/uv) to install dependencies:
        ```bash
        uv sync
        ```

3.  **Configure Environment Variables:**
    *   Create a `.env` file in the root directory and put your credentials there.   
    *   Fill in the required API keys and tokens in your `.env` file:
        *   `TELEGRAM_BOT_TOKEN`: Your Telegram Bot token from BotFather.
        *   `TAVILY_API_KEY`: Your Tavily Search API key.
        *   `GEMINI_API_KEY`: API key for the LLM used by BAML.
        *   *(Add any other keys required by `config.py`)*

## ▶️ Usage

1.  **(Optional) Run the Agent Script Directly (for testing):**
    *   You can test the core agent logic by running `agent.py`. Modify the example URL within the script if needed.
    ```bash
    python agent.py
    ```

2.  **(Optional) Deploy to LangGraph Studio:**
    *   If you have the LangGraph CLI installed (`pip install langgraph-cli`), you can deploy your agent graph for monitoring and debugging:
    ```bash
    langgraph deploy
    ```
    *   Follow the CLI prompts to name your deployment.

3.  **Start the Telegram Bot (Primary Usage):**
    *   **Note:** This interface is currently untested.
    ```bash
    python bot.py
    ```

4.  **Interact with the Bot:**
    *   Open Telegram and find the bot you created.
    *   Send a message containing a URL (e.g., `https://example.com/article`).
    *   The bot will process the link and reply with a summary.

## 📊 Agent Visualization

The `agent_viz.py` script can be used to generate a visualization of the LangGraph agent (like the image at the top). Run it if needed:

```bash
marimo edit agent_viz.py
```

This will open marimo and you can run and visualize the agent graph flow.

## Local Running

This runs the FastAPI server directly. Note that without a publicly accessible `WEBHOOK_URL`, the bot will not receive messages from Telegram.

```bash
uvicorn bot:app --host 0.0.0.0 --port 8080 --reload
```

You can check if the server is running by accessing the health check endpoint: `curl http://localhost:8080/health`

To test receiving actual Telegram messages locally, you'll need a tool like `ngrok` to create a public tunnel to your `localhost:8080` and set the ngrok URL as `WEBHOOK_URL` in your `.env` file.

## Docker Testing

1.  **Build the Docker Image:**
    ```bash
    docker build -t telegram-summarizer .
    ```
2.  **Run the Docker Container:** (Ensure your `.env` file is in the current directory)
    ```bash
    docker run -p 8080:8080 --rm --name summarizer-bot --env-file .env telegram-summarizer
    ```
    You can check the health endpoint at `http://localhost:8080/health`.

## Cloud Run Deployment

This guide assumes you have a GCP account, `gcloud` CLI installed and configured, and Docker installed.

1.  **Set Environment Variables (Shell):**
    ```bash
    export PROJECT_ID="your-gcp-project-id"
    export REGION="your-preferred-region" # e.g., us-central1
    export SERVICE_NAME="telegram-summarizer"
    export REPO_NAME="bots" # Or your preferred Artifact Registry repo name
    export IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

    gcloud config set project $PROJECT_ID
    gcloud config set run/region $REGION
    ```
2.  **Enable Required APIs:**
    ```bash
    gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
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
    ```
5.  **Build and Push Image using Cloud Build:**
    ```bash
    gcloud builds submit --tag $IMAGE_NAME .
    ```
6.  **Initial Deploy to Cloud Run (without Webhook URL):**
    CRITICAL: You must get the service URL after the initial deployment and use it for the WEBHOOK_URL. Cloud Run provides a stable HTTPS URL.
    You can deploy once without WEBHOOK_URL, get the URL, then deploy again setting it. Or, use a placeholder and update it. Let's deploy setting the essential variables first. Make sure your .env file secrets are secure (don't commit it!). It's better to pass secrets directly during deployment.

    Pass secrets securely (avoid hardcoding in scripts).
    ```bash
    # Example: Get secrets from environment or prompts
    # Ensure TELEGRAM_BOT_TOKEN_SECRET, TAVILY_API_KEY_SECRET etc. are set

    gcloud run deploy $SERVICE_NAME \
      --image $IMAGE_NAME \
      --platform managed \
      --port 8080 \
      --allow-unauthenticated \
      --set-env-vars="TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN_SECRET}" \
      --set-env-vars="TAVILY_API_KEY=${TAVILY_API_KEY_SECRET}" \
      # Add other --set-env-vars="KEY=VALUE" as needed
      --region $REGION \
      --min-instances 0 # Scale-to-zero
    ```
7.  **Get Service URL & Update Deployment with Webhook:**
    ```bash
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
    echo "Service URL: $SERVICE_URL"

    # Optional: Define WEBHOOK_SECRET_PATH and TELEGRAM_WEBHOOK_SECRET_TOKEN here if desired
    # WEBHOOK_SECRET_PATH_VALUE="your-random-secret-path-segment"
    # WEBHOOK_SECRET_TOKEN_VALUE="your-random-secret-token"

    gcloud run deploy $SERVICE_NAME \
      --image $IMAGE_NAME \
      --platform managed \
      --port 8080 \
      --allow-unauthenticated \
      --update-env-vars="WEBHOOK_URL=${SERVICE_URL}" \
      # Add other --update-env-vars here if needed, e.g.:
      # --update-env-vars="WEBHOOK_SECRET_PATH=${WEBHOOK_SECRET_PATH_VALUE}" \
      # --update-env-vars="TELEGRAM_WEBHOOK_SECRET_TOKEN=${WEBHOOK_SECRET_TOKEN_VALUE}" \
      --region $REGION
    ```
    Your bot should now be running on Cloud Run and have its webhook set with Telegram.