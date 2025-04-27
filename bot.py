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

# --- Message Handler --- 
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, extracts URLs, triggers the agent,
    and replies with a summary, a screenshot + fallback text, or an error."""
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

    agent_result = None # Initialize
    try:
        # Run the agent (now async)
        # Expecting:
        # - Tuple[bytes, str]: Screenshot + summary when both are available
        # - Tuple[bytes, str|None]: Screenshot + fallback content (or None)
        # - str: Summary text or error message
        # - None: Unexpected failure
        agent_result = await run_agent(text) # Pass the original message
        
        # Debug logging to see what we got from the agent
        if isinstance(agent_result, tuple):
            logger.info(f"Agent returned a tuple: {type(agent_result)} with {len(agent_result)} items")
            if len(agent_result) >= 1:
                logger.info(f"First item type: {type(agent_result[0])}")
                if isinstance(agent_result[0], bytes):
                    logger.info(f"Screenshot size: {len(agent_result[0])} bytes")
            if len(agent_result) >= 2:
                logger.info(f"Second item type: {type(agent_result[1])}")
                if isinstance(agent_result[1], str):
                    logger.info(f"Text content length: {len(agent_result[1])} chars")
        elif isinstance(agent_result, str):
            logger.info(f"Agent returned a string of length {len(agent_result)}")
        else:
            logger.info(f"Agent returned type: {type(agent_result)}")

        MAX_LEN = 4096 # Max Telegram message length

        # --- Handle Tuple Result (Screenshot + Text) ---
        if isinstance(agent_result, tuple) and len(agent_result) == 2:
            screenshot_bytes, text_content = agent_result
            
            # Send screenshot if available
            if isinstance(screenshot_bytes, bytes):
                logger.info(f"Sending screenshot to chat {chat_id} for URL: {url}")
                
                # Determine if this is a summary or fallback content
                is_summary = text_content and not text_content.startswith("Fallback Content:")
                
                # Set appropriate caption
                if is_summary:
                    caption = f"Screenshot for: {url}"
                else:
                    caption = f"Screenshot for: {url}"
                    if not text_content:
                        caption += "\n(Content extraction failed)"
                
                try:
                    # Send the screenshot
                    await message.reply_photo(photo=screenshot_bytes, caption=caption)
                    logger.info(f"Successfully sent screenshot to chat {chat_id}")
                except Exception as photo_err:
                    logger.error(f"Failed to send photo: {photo_err}")
                    # Try sending as document if photo fails
                    try:
                        logger.info("Trying to send as document instead...")
                        await message.reply_document(document=screenshot_bytes, caption=caption)
                        logger.info(f"Successfully sent screenshot as document to chat {chat_id}")
                    except Exception as doc_err:
                        logger.error(f"Failed to send document too: {doc_err}")
            else:
                logger.warning(f"Agent returned tuple but no screenshot bytes for {url}. Type: {type(screenshot_bytes)}")

            # Send text content if available (either summary or fallback content)
            if isinstance(text_content, str) and text_content:
                logger.info(f"Sending {'summary' if is_summary else 'fallback content'} to chat {chat_id} for URL: {url}")
                escaped_content = html.escape(text_content)
                if len(escaped_content) > MAX_LEN:
                    escaped_content = escaped_content[:MAX_LEN-20] + "... (truncated)"
                await message.reply_text(escaped_content, parse_mode=ParseMode.HTML)
                logger.info(f"Sent text content to chat {chat_id}")

        # --- Handle String Result (Summary or Error) ---
        elif isinstance(agent_result, str) and agent_result:
            # Check if it's an error message from the agent
            if agent_result.startswith("Error:"):
                logger.error(f"Agent returned an error for chat {chat_id} (URL: {url}): {agent_result}")
                escaped_error = html.escape(agent_result)
                if len(escaped_error) > MAX_LEN:
                    escaped_error = escaped_error[:MAX_LEN-20] + "... (error truncated)"
                await message.reply_text(escaped_error, parse_mode=ParseMode.HTML)
            
            # Otherwise, it's a summary or fallback content
            else:
                content_type = "fallback content" if agent_result.startswith("Fallback Content:") else "summary"
                logger.info(f"Sending {content_type} back to chat {chat_id} for URL: {url}")
                escaped_result = html.escape(agent_result)
                if len(escaped_result) > MAX_LEN:
                    escaped_result = escaped_result[:MAX_LEN-20] + f"... ({content_type} truncated)"
                await message.reply_text(escaped_result, parse_mode=ParseMode.HTML)
                logger.info(f"Sent {content_type} back to chat {chat_id}")

        # --- Handle Failure (None or Unexpected Type) ---
        else:
            error_info = f"Type: {type(agent_result)}" if agent_result is not None else "None"
            logger.warning(f"Agent returned unexpected result ({error_info}) for chat {chat_id} and URL {url}. No reply sent.")
            # Optionally send a generic failure message
            # await message.reply_text("Sorry, failed to process the URL.")

    except Exception as e:
        # Log any exception during agent execution or message handling
        logger.error(f"Error handling message for chat {chat_id} (URL: {url}): {e}", exc_info=True)
        # Send a generic error message to the user
        error_message = f"Sorry, an unexpected error occurred while processing your request for {url}."
        try:
            await message.reply_text(html.escape(error_message), parse_mode=ParseMode.HTML)
        except Exception as send_err:
            logger.error(f"Failed to send error message to chat {chat_id}: {send_err}")


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
