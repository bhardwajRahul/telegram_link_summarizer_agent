import logging
import re
import html # For escaping HTML in messages
import os
from contextlib import asynccontextmanager 
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Response, HTTPException, Header, APIRouter 
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
    summary_or_error = None # Initialize
    try:
        # Run the agent. Expecting a summary string on success,
        # or potentially None/empty string/error string on failure within the agent.
        summary_or_error = run_agent(text)

        # Check if the agent indicated an error or returned no summary
        if not summary_or_error:
            logger.warning(f"Agent returned no summary or indicated an error for chat {chat_id} and URL {url}. No reply sent.")
            # Optionally, log the specific error if the agent returns it distinctly
            # if isinstance(summary_or_error, str) and summary_or_error.startswith("Error:"):
            #     logger.error(f"Agent error for chat {chat_id}: {summary_or_error}")
            return # Exit without sending a message

        # Escape HTML characters in the result to prevent formatting issues
        # Limit message length to Telegram's max (4096 chars)
        MAX_LEN = 4096
        escaped_result = html.escape(summary_or_error)
        if len(escaped_result) > MAX_LEN:
            escaped_result = escaped_result[:MAX_LEN-10] + "... (truncated)"

        # Send the result back ONLY if successful
        await message.reply_text(escaped_result, parse_mode=ParseMode.HTML)
        logger.info(f"Sent summary back to chat {chat_id}")

    except Exception as e:
        # Log any exception during agent execution or message handling
        logger.error(f"Error handling message for chat {chat_id} (URL: {url}): {e}", exc_info=True)
        # DO NOT send an error message back to the chat per user request
        # error_message = f"Sorry, an error occurred: {html.escape(str(e))}"
        # await message.reply_text(error_message[:4096], parse_mode=ParseMode.HTML)

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
            full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{WEBHOOK_SECRET_PATH.lstrip('/')}"
            logger.info(f"Setting webhook for URL: {full_webhook_url}")
            await ptb_app.bot.set_webhook(
                url=full_webhook_url, 
                secret_token=os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN"),
                allowed_updates=Update.ALL_TYPES # Optional: specify which updates you want
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
async def webhook(
    request: Request, 
    secret_token: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token") # Add this parameter
) -> Response:
    """Handles incoming Telegram updates via webhook."""
    # --- Webhook Secret Token Verification ---
    TELEGRAM_WEBHOOK_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
    if TELEGRAM_WEBHOOK_SECRET_TOKEN and secret_token != TELEGRAM_WEBHOOK_SECRET_TOKEN:
         logger.warning("Invalid secret token received.")
         raise HTTPException(status_code=403, detail="Invalid secret token")
    # --- End Verification ---
    
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
    """Basic health check endpoint."""
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

# --- Main Execution Block (for running with uvicorn) ---
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    
    # Check if we should run in polling mode (for local testing without webhook)
    use_polling = os.getenv("USE_POLLING", "false").lower() == "true"
    
    if use_polling:
        logger.info("Starting bot in polling mode...")
        # Register the message handler
        url_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
        ptb_app.add_handler(url_handler)
        
        # Start the bot in polling mode
        logger.info("Starting polling...")
        ptb_app.run_polling()
    else:
        # Run in webhook mode with FastAPI
        logger.info(f"Starting Uvicorn server on {host}:{port}...")
        uvicorn.run(app, host=host, port=port)
