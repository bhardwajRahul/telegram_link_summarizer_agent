# config.py

import os
from dotenv import load_dotenv
import logging

# Load environment variables from.env file
load_dotenv()

logger = logging.getLogger(__name__)


def get_env_variable(var_name: str, default_value: str | None = None) -> str:
    """Gets an environment variable or raises an error if not found and no default is provided."""
    value = os.getenv(var_name, default_value)
    if value is None:
        logger.error(
            f"Environment variable '{var_name}' not found and no default value provided."
        )
        raise ValueError(f"Missing required environment variable: '{var_name}'")
    return value


def get_int_env_variable(var_name: str, default_value: int | None = None) -> int:
    """Gets an integer environment variable."""
    value_str = get_env_variable(
        var_name, str(default_value) if default_value is not None else None
    )
    try:
        return int(value_str)
    except ValueError:
        logger.error(
            f"Environment variable '{var_name}' must be an integer. Found: '{value_str}'"
        )
        raise ValueError(
            f"Invalid integer value for environment variable: '{var_name}'"
        )


# --- Core API Keys ---
TELEGRAM_BOT_TOKEN: str = get_env_variable("TELEGRAM_BOT_TOKEN")

# --- Tool API Keys ---
FIRECRAWL_API_KEY: str | None = os.getenv("FIRECRAWL_API_KEY")
TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")

# --- LLM & RAG Settings ---
EMBEDDING_MODEL_NAME: str = get_env_variable("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# --- System Behavior ---
RAG_THRESHOLD: int = get_int_env_variable("RAG_THRESHOLD", 3000)
ALLOWED_CHAT_ID: str | None = os.getenv(
    "ALLOWED_CHAT_ID"
)  # Optional: Restrict bot to a specific chat

# --- Logging Configuration ---
LOGGING_LEVEL = logging.INFO  # Set to logging.DEBUG for more verbose output

# Basic logging setup
logging.basicConfig(
    level=LOGGING_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger.info("Configuration loaded successfully.")
if not FIRECRAWL_API_KEY:
    logger.warning(
        "FIRECRAWL_API_KEY not set. Firecrawl scraping fallback will not be available."
    )
if not TAVILY_API_KEY:
    logger.warning("TAVILY_API_KEY not set. Tavily search tool will not be available.")
if ALLOWED_CHAT_ID:
    logger.info(f"Bot restricted to chat ID: {ALLOWED_CHAT_ID}")
else:
    logger.info("Bot will respond in any chat it's added to.")
