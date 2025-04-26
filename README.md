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

2.  **Set up Python Environment:**
    *   Ensure you have Python 3.11 or higher.
    *   (Optional, Recommended) Create and activate a virtual environment:
        ```bash
        python -m venv .venv
        source .venv/bin/activate # On Windows use `.venv\Scripts\activate`
        ```

3.  **Install Dependencies:**
    *   Using `uv` (recommended, if installed):
        ```bash
        uv pip install -r requirements.txt # Or potentially 'uv pip install .' if pyproject is fully configured
        ```
    *   Using `pip`:
        ```bash
        pip install -r requirements.txt # Or 'pip install .'
        ```
    *(Note: Verify the exact command based on `pyproject.toml` setup; `requirements.txt` might not be the primary source if using `uv` or modern `pip` with `pyproject.toml`)*

4.  **Configure Environment Variables:**
    *   Copy the example environment file (if one exists, e.g., `.env.example`) or create a `.env` file:
        ```bash
        cp .env.example .env # Or create .env manually
        ```
    *   Fill in the required API keys and tokens in your `.env` file:
        *   `TELEGRAM_BOT_TOKEN`: Your Telegram Bot token from BotFather.
        *   `TAVILY_API_KEY`: Your Tavily Search API key.
        *   `BOUNDARY_API_KEY` or `OPENAI_API_KEY`: API key for the LLM used by BAML/LangChain.
        *   *(Add any other keys required by `config.py`)*

## ▶️ Usage

1.  **Run the BAML Language Server (if required by your BAML setup):**
    *   Check BAML documentation for how to run its server component if needed.

2.  **Start the Telegram Bot:**
    ```bash
    python bot.py
    ```

3.  **Interact with the Bot:**
    *   Open Telegram and find the bot you created.
    *   Send a message containing a URL (e.g., `https://example.com/article`).
    *   The bot will process the link and reply with a summary.

## 📊 Agent Visualization

The `agent_viz.py` script can be used to generate a visualization of the LangGraph agent (like the image at the top). Run it if needed:

```bash
python agent_viz.py
```

This will likely save or display the graph.

## 📄 License

(Specify your license here, e.g., MIT License)