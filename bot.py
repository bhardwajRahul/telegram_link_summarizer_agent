import logging
import re
import html # For escaping HTML in messages
import os
from contextlib import asynccontextmanager 
from dotenv import load_dotenv

from fastapi import FastAPI, Request 
import uvicorn 

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import the agent runner
from agent import run_agent

# Load environment variables from .env file
load_dotenv(override=True)

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Constants ---
# Simple regex to find the first URL in a message
URL_REGEX = r'(https?://\S+)'

# --- Environment Variables & Constants ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "webhook")

if not BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN missing. Bot cannot start.")
    exit()

if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL missing. Webhook setup will be skipped (local testing?).")


# --- Global Application Object ---
ptb_app = Application.builder().token(BOT_TOKEN).build()

# --- Message Handler (Keep existing logic) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, extracts URLs, and triggers the summarizer agent."""
    message = update.effective_message
    chat_id = message.chat_id
    text = message.text

    if not text:
        return

    # Find the first URL in the message
    match = re.search(URL_REGEX, text)
    if not match:
        # logger.debug("No URL found in message.")
        return # Ignore messages without URLs

    url = match.group(1)
    logger.info(f"URL detected in chat {chat_id}: {url}")

    # Send a typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    # Pass the original message text to the agent, as it might contain context/query
    # Or just pass the URL if the agent's start_node is designed for that
    # Current agent.run_agent expects the full message text
    try:
        summary_or_error = run_agent(text) 

        # Escape HTML characters in the result to prevent formatting issues
        # Limit message length to Telegram's max (4096 chars)
        MAX_LEN = 4096
        escaped_result = html.escape(summary_or_error)
        if len(escaped_result) > MAX_LEN:
            escaped_result = escaped_result[:MAX_LEN-10] + "... (truncated)"

        # Send the result back
        # Consider using message threads if available/appropriate
        await message.reply_text(escaped_result, parse_mode=ParseMode.HTML)
        logger.info(f"Sent summary/error back to chat {chat_id}")

    except Exception as e:
        logger.error(f"Error handling message for chat {chat_id}: {e}", exc_info=True)
        error_message = f"Sorry, an error occurred: {html.escape(str(e))}"
        await message.reply_text(error_message[:4096], parse_mode=ParseMode.HTML)

# --- FastAPI Lifespan Management (Setup/Teardown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup --- 
    logger.info("Application startup...")
    url_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    ptb_app.add_handler(url_handler)

    if WEBHOOK_URL:
        full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{WEBHOOK_SECRET_PATH}"
        logger.info(f"Setting webhook to: {full_webhook_url}")
        try:
            await ptb_app.initialize() 
            await ptb_app.bot.set_webhook(
                url=full_webhook_url,
                allowed_updates=Update.ALL_TYPES,
                secret_token=os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN") 
            )
            await ptb_app.start() 
            logger.info("Webhook set successfully.")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
            # Decide if you want to exit or continue without webhook
            # exit() 
    else:
        logger.warning("WEBHOOK_URL not set, skipping webhook setup. Bot will not receive updates via webhook.")

    yield 

    # --- Shutdown ---
    logger.info("Application shutdown...")
    if WEBHOOK_URL: 
        try:
            logger.info("Attempting to delete webhook...")
            await ptb_app.bot.delete_webhook()
            logger.info("Webhook deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete webhook during shutdown: {e}", exc_info=True)
        finally:
            await ptb_app.stop()
            await ptb_app.shutdown()
            logger.info("PTB Application stopped and shut down.")
    else:
        logger.info("No webhook was set, shutdown complete.")


# --- FastAPI Application Definition ---
app = FastAPI(lifespan=lifespan)

# --- Webhook Endpoint ---
@app.post(f"/{WEBHOOK_SECRET_PATH}")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates via webhook."""
    try:
        update_data = await request.json()
        update = Update.de_json(update_data, ptb_app.bot)
        logger.debug(f"Received update: {update.update_id}")
        await ptb_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

# --- Health Check Endpoint (Good Practice) ---
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# --- Main Execution Block (for running with uvicorn) ---
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))

    logger.info(f"Starting Uvicorn server on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
