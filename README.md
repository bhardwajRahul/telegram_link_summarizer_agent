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

## Testing Webhooks Locally with ngrok

When running your bot locally, Telegram cannot reach your computer directly because `localhost` is not accessible from the public internet. To test real Telegram messages with webhooks during development, you can use [ngrok](https://ngrok.com/) to create a secure tunnel from a public URL to your local machine.

### Steps

1. **Install ngrok:**
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

2. **Start your local server:**
   ```bash
   uvicorn bot:app --host 0.0.0.0 --port 8080 --reload
   ```

3. **Start ngrok to expose port 8080:**
   ```bash
   ngrok http 8080
   ```
   - You will see output like:
     ```
     Forwarding https://abcd-1234.ngrok-free.app -> http://localhost:8080
     ```
   - Copy the HTTPS URL provided by ngrok (e.g., `https://abcd-1234.ngrok-free.app`).

4. **Update your `.env` file:**
   - Set the `WEBHOOK_URL` to the ngrok HTTPS URL:
     ```env
     WEBHOOK_URL=https://abcd-1234.ngrok-free.app
     ```
   - Save the file.

5. **Restart your local server:**
   - Stop the running `uvicorn` process (Ctrl+C) and start it again:
     ```bash
     uvicorn bot:app --host 0.0.0.0 --port 8080 --reload
     ```
   - On startup, the bot will register the webhook with Telegram using your public ngrok URL.

6. **Test your bot:**
   - Send a message with a link to your Telegram bot as usual.
   - Telegram will send the update to your ngrok public URL, which forwards it to your local server.
   - You should see logs in your terminal and receive a response from your local bot.

**Tip:** If you restart ngrok, you will get a new public URL. Update your `.env` and restart the server each time.

**Security Note:** For production, always use a secret path and/or secret token for your webhook endpoint. For local testing, the default `/webhook` is sufficient, but you can configure a custom path using the `WEBHOOK_SECRET_PATH` variable.

## Docker Testing

1.  **Build the Docker Image:**
    ```bash
    docker build -t telegram-summarizer .
    ```
2.  **Run the Docker Container:** (Ensure your `.env` file is in the current directory)
    ```bash
    docker run -p 8080:8080 --rm --name summarizer-bot --env-file .env telegram-summarizer
    ```
    You can check the health endpoint at `http://localhost:8080/health`

## Deploying to Google Cloud Run

This guide assumes you have a GCP account, `gcloud` CLI installed and configured, and Docker installed.

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
    ```
5.  **Manage Secrets with Secret Manager (Recommended):**
    Store API keys and tokens securely using Google Cloud Secret Manager. You can use the `gcloud` CLI:

    *   **Create Secret:** (Do this once per secret, e.g., `telegram-bot-token`, `tavily-api-key`)
        ```bash
        gcloud secrets create telegram-bot-token --replication-policy="automatic"
        gcloud secrets create tavily-api-key --replication-policy="automatic"
        gcloud secrets create telegram-webhook-secret-token --replication-policy="automatic" # For verifying requests *from* Telegram
        gcloud secrets create webhook-secret-path --replication-policy="automatic"           # For the URL path the bot listens *on*
        gcloud secrets create deepseek-api-key --replication-policy="automatic"
        gcloud secrets create gemini-api-key --replication-policy="automatic"
        # Add others as needed (e.g., openai-api-key)
        ```
    *   **Add Secret Value:** (Use stdin for security)
        Generate your secret strings (e.g., using `openssl rand -hex 32`). You can use the same string for both or different ones (recommended).
        ```bash
        echo "Adding Telegram Bot Token: Paste token then Ctrl+D"
        gcloud secrets versions add telegram-bot-token --data-file=-

        echo "Adding Tavily API Key: Paste key then Ctrl+D"
        gcloud secrets versions add tavily-api-key --data-file=-
        
        echo "Adding Telegram Webhook Secret Token (for verification): Paste your chosen secret string then Ctrl+D"
        gcloud secrets versions add telegram-webhook-secret-token --data-file=-
        
        echo "Adding Webhook Secret Path (for URL): Paste your chosen secret string then Ctrl+D"
        gcloud secrets versions add webhook-secret-path --data-file=-

        echo "Adding DeepSeek API Key: Paste key then Ctrl+D"
        gcloud secrets versions add deepseek-api-key --data-file=-

        echo "Adding Gemini API Key: Paste key then Ctrl+D"
        gcloud secrets versions add gemini-api-key --data-file=-
        
        # Add versions for other secrets...
        ```
    *   **Grant Access to Cloud Run Service Account:** (Find `PROJECT_NUMBER` with `gcloud projects describe $PROJECT_ID --format='value(projectNumber)'`)
        ```bash
        PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
        GCP_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

        gcloud secrets add-iam-policy-binding telegram-bot-token \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        gcloud secrets add-iam-policy-binding tavily-api-key \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        gcloud secrets add-iam-policy-binding telegram-webhook-secret-token \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        gcloud secrets add-iam-policy-binding webhook-secret-path \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        gcloud secrets add-iam-policy-binding deepseek-api-key \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        gcloud secrets add-iam-policy-binding gemini-api-key \
          --member="serviceAccount:${GCP_SERVICE_ACCOUNT}" \
          --role="roles/secretmanager.secretAccessor"
          
        # Add bindings for DeepSeek, Gemini, etc.
        ```

6.  **Build and Push Image using Cloud Build:**
    ```bash
    gcloud builds submit --tag $IMAGE_NAME .
    ```
7.  **Initial Deploy to Cloud Run (Setting Secrets):**
    *   **Public Access:** The `--allow-unauthenticated` flag is **required** for Telegram webhooks to reach your service. See the Security section below.
    *   **Secrets:** Use `--set-secrets` to securely mount secrets from Secret Manager as environment variables.

    ```bash
    gcloud run deploy $SERVICE_NAME \
      --image $IMAGE_NAME \
      --platform managed \
      --port 8080 \
      --allow-unauthenticated \
      --set-secrets="TELEGRAM_BOT_TOKEN=telegram-bot-token:latest" \
      --set-secrets="TAVILY_API_KEY=tavily-api-key:latest" \
      --set-secrets="TELEGRAM_WEBHOOK_SECRET_TOKEN=telegram-webhook-secret-token:latest" \
      --set-secrets="WEBHOOK_SECRET_PATH=webhook-secret-path:latest" \
      --set-secrets="DEEPSEEK_API_KEY=deepseek-api-key:latest" \
      --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
      --region $REGION \
      --min-instances 0 # Scale-to-zero
    ```
8.  **Get Service URL & Update Deployment with Webhook URL:**
    ```bash
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
    echo "Service URL: $SERVICE_URL"
    ```
 
    ```bash
    gcloud run deploy $SERVICE_NAME \
      --image $IMAGE_NAME \
      --platform managed \
      --port 8080 \
      --allow-unauthenticated \
      --update-env-vars="WEBHOOK_URL=${SERVICE_URL}" \
      --update-secrets="TELEGRAM_WEBHOOK_SECRET_TOKEN=telegram-webhook-secret-token:latest" \
      --update-secrets="WEBHOOK_SECRET_PATH=webhook-secret-path:latest" \
      --update-secrets="DEEPSEEK_API_KEY=deepseek-api-key:latest" \
      --update-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
      --region $REGION
    ```
 
### Securing the Public Endpoint

Since the service uses `--allow-unauthenticated`, it's crucial to secure it. We use two methods:

1.  **Webhook Secret Token (`TELEGRAM_WEBHOOK_SECRET_TOKEN`):** Verifies incoming requests *are from* Telegram using the `X-Telegram-Bot-Api-Secret-Token` header.
2.  **Secret URL Path (`WEBHOOK_SECRET_PATH`):** Makes the endpoint URL path unpredictable (e.g., `https://.../your-secret-path` instead of `https://.../webhook`). The bot listens *only* on this path.

Implement these using environment variables set via Secret Manager:

Steps:

*   # 1. Generate strong random secret strings (use different ones for better security):
    #    SECRET_TOKEN_VALUE=$(openssl rand -hex 32)
    #    SECRET_PATH_VALUE=$(openssl rand -hex 32)
    #    echo "Webhook Secret Token: ${SECRET_TOKEN_VALUE}" # Save securely!
    #    echo "Webhook Secret Path:  ${SECRET_PATH_VALUE}" # Save securely!
*   # 2. Add these values to the secrets created earlier in the main deployment steps:
    #    echo ${SECRET_TOKEN_VALUE} | gcloud secrets versions add telegram-webhook-secret-token --data-file=-
    #    echo ${SECRET_PATH_VALUE}  | gcloud secrets versions add webhook-secret-path --data-file=-
*   # 3. Ensure the service account has access (as shown in the main deployment steps).
*   # 4. Ensure the bot.py code uses WEBHOOK_SECRET_PATH when registering the webhook
    #    and verifies TELEGRAM_WEBHOOK_SECRET_TOKEN on incoming requests (next step).

Your bot should now be running on Cloud Run, have its webhook set with Telegram, and be secured against unauthorized requests.