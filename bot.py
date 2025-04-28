import logging
import os
from contextlib import asynccontextmanager 
from dotenv import load_dotenv
import asyncio
import re
import html  # <-- Add this import

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
URL_REGEX = r'(https?:\/\/[^\s]+)'

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
    message = update.effective_message
    text = message.text
    chat_id = message.chat_id
    logger.info(f"Received message in chat {chat_id}: {text}")

    # Simple check for URL
    if not any(url in text for url in ['http://', 'https://']):
        logger.info("Message does not contain a URL, ignoring.")
        return

    # Extract the first URL
    url_match = re.search(URL_REGEX, text)
    if not url_match:
        logger.info("No URL found in the message despite initial check.") # Should not happen often
        return

    extracted_url = url_match.group(0)
    logger.info(f"Extracted URL: {extracted_url}")

    # Send a thinking message
    thinking_message = await message.reply_text(" Thinking...")

    try:
        # Run the agent
        agent_result = await run_agent(text)

        # Delete the thinking message
        await context.bot.delete_message(chat_id=chat_id, message_id=thinking_message.message_id)

        # --- Process Agent Result --- 
        MAX_CAPTION_LEN = 1024 # Telegram caption limit
        MAX_LEN = 4096 # Max Telegram message length
        
        if isinstance(agent_result, tuple) and len(agent_result) == 2:
            screenshot_bytes, text_to_send = agent_result
            logger.info(f"Agent returned screenshot ({len(screenshot_bytes)} bytes) and text (len {len(str(text_to_send))} chars)")

            # Ensure text_to_send is a string
            if not isinstance(text_to_send, str):
                text_to_send = f"Error: Agent returned non-string text content (Type: {type(text_to_send).__name__})"
                logger.error(f"Agent returned non-string text for caption: {type(text_to_send).__name__}")

            # --- Construct the caption with the URL ---
            url_prefix = f"{extracted_url}\n\n"
            caption_base = url_prefix + text_to_send
            caption = caption_base

            # Truncate caption if necessary
            if len(caption) > MAX_CAPTION_LEN:
                logger.warning(f"Caption (len {len(caption)}) exceeds max length ({MAX_CAPTION_LEN}). Truncating summary part.")
                available_len = MAX_CAPTION_LEN - len(url_prefix) - 3 # Account for URL, prefix, and "..."
                if available_len > 0:
                    truncated_summary = text_to_send[:available_len] + "..."
                    caption = url_prefix + truncated_summary
                else:
                    # If URL itself is too long, just truncate the whole thing (edge case)
                    caption = caption_base[:MAX_CAPTION_LEN - 3] + "..."
            # --- End Caption Construction ---

            try:
                logger.info(f"Attempting to send photo with caption (caption len: {len(caption)})...")
                await context.bot.send_photo(
                    chat_id=chat_id,
                    reply_to_message_id=message.message_id,
                    photo=screenshot_bytes,
                    caption=caption,
                    parse_mode=ParseMode.HTML # Make sure summary doesn't contain conflicting HTML
                )
                logger.info("Successfully sent photo with caption.")
            except Exception as e_photo:
                logger.warning(f"Failed to send as photo: {e_photo}. Trying as document.")
                try:
                    logger.info(f"Attempting to send document with caption (caption len: {len(caption)})...")
                    await context.bot.send_document(
                        chat_id=chat_id,
                        reply_to_message_id=message.message_id,
                        document=screenshot_bytes,
                        filename="screenshot.png",
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                    logger.info("Successfully sent document with caption.")
                except Exception as e_doc:
                    logger.error(f"Failed to send as document with caption: {e_doc}.")
                    await message.reply_text(f"Failed to send screenshot (Error: {e_doc}). You can view the summary below.")
                    # Send summary text separately if media fails
                    for i in range(0, len(text_to_send), MAX_LEN):
                         chunk = text_to_send[i:i + MAX_LEN]
                         await message.reply_text(chunk, parse_mode=ParseMode.HTML)
                         if i + MAX_LEN < len(text_to_send):
                             await asyncio.sleep(0.5)


        elif isinstance(agent_result, str):
            # Only text was returned
            logger.info(f"Agent returned only text (len {len(agent_result)} chars). Sending text message.")
            
            # Escape HTML characters to prevent parsing errors using built-in html module
            text_to_send = html.escape(agent_result)
            
            # Send text in chunks if too long
            for i in range(0, len(text_to_send), MAX_LEN):
                chunk = text_to_send[i:i + MAX_LEN]
                await message.reply_text(chunk, parse_mode=ParseMode.HTML)
                if i + MAX_LEN < len(text_to_send):
                    await asyncio.sleep(0.5) # Small delay between chunks

        else:
            logger.error(f"Agent returned unexpected result type: {type(agent_result)}")
            await message.reply_text("Sorry, I received an unexpected result from the agent.")

    except Exception as e:
        logger.error(f"Error handling message for URL {extracted_url}: {e}", exc_info=True)
        error_message = f"❌ An error occurred: {e}"
        try:
            # Escape the error message for HTML parsing
            escaped_error_message = html.escape(str(error_message))
            # Wrap in <pre> tags for preformatted text
            formatted_error_message = f"<pre>{escaped_error_message}</pre>"
            # Send potentially long errors in chunks
            for chunk in [formatted_error_message[i:i + MAX_LEN] for i in range(0, len(formatted_error_message), MAX_LEN)]:
                await message.reply_text(chunk, parse_mode=ParseMode.HTML)
        except Exception as send_error:
            logger.error(f"Failed to send error message to chat {chat_id}: {send_error}", exc_info=True)
            # Fallback to sending plain text if HTML fails
            try:
                # Ensure fallback message is also chunked
                fallback_msg = f"An error occurred, and I couldn't format the details: {e}"
                for chunk in [fallback_msg[i:i + MAX_LEN] for i in range(0, len(fallback_msg), MAX_LEN)]:
                    await message.reply_text(chunk) # Send as plain text
            except Exception as fallback_send_error:
                logger.error(f"Failed to send even plain text error message: {fallback_send_error}", exc_info=True)
    finally:
        # Delete the 'thinking' message if it exists
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=thinking_message.message_id)
        except Exception as del_e:
            logger.error(f"Failed to delete thinking message: {del_e}")


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
