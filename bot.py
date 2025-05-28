import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncio
import re
import html  # <-- Add this import
import json

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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Constants ---
# Simple regex to find the first URL in a message
URL_REGEX = r"(https?:\/\/[^\s]+)"

# --- Environment Variables & Constants ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# For Cloud Run, we should use the service URL as the webhook URL
# if not explicitly set through WEBHOOK_URL
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "webhook")

# If we're in Cloud Run, we'll see these environment variables
CLOUD_RUN_SERVICE_URL = os.getenv("K_SERVICE")  # Will be set in Cloud Run

if not BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN missing. Bot cannot start.")
    exit()

# If we're in Cloud Run but no WEBHOOK_URL is set, use inference
if CLOUD_RUN_SERVICE_URL and not WEBHOOK_URL:
    WEBHOOK_URL = f"https://{os.getenv('K_SERVICE')}-{os.getenv('K_REVISION', 'latest')}.{os.getenv('K_REGION', 'unknown')}.run.app"
    logger.info(f"Running in Cloud Run, inferred WEBHOOK_URL: {WEBHOOK_URL}")

if not WEBHOOK_URL:
    logger.warning(
        "WEBHOOK_URL missing. Webhook setup will be skipped (local testing?)."
    )


# --- Global Application Object ---
ptb_app = Application.builder().token(BOT_TOKEN).build()


# --- Message Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = message.text
    chat_id = message.chat_id
    logger.info(f"Received message in chat {chat_id}: {text}")

    # Simple check for URL
    if not any(url in text for url in ["http://", "https://"]):
        logger.info("Message does not contain a URL, ignoring.")
        return

    # Extract the first URL
    url_match = re.search(URL_REGEX, text)
    if not url_match:
        logger.info("No URL found in the message despite initial check. Ignoring.")
        return

    extracted_url = url_match.group(0)
    logger.info(f"Extracted URL: {extracted_url}")

    try:
        # Run the agent
        agent_result = await run_agent(text)

        # --- Process Agent Result ---
        MAX_LEN = 4096  # Max Telegram message length

        # Agent returns string (summary or error) or None.
        # Only proceed if we got a valid summary string (not starting with "Error:").
        if isinstance(agent_result, str) and not agent_result.startswith("Error:"):
            logger.info(
                f"Agent returned valid summary (len {len(agent_result)} chars). Preparing message."
            )

            # Use agent result directly as the raw text to send (URL removed)
            text_to_send_raw = agent_result

            # Escape HTML characters for summary part to prevent parsing errors
            text_to_send_formatted = html.escape(agent_result)

            # Send text in chunks if too long
            for i in range(0, len(text_to_send_formatted), MAX_LEN):
                chunk = text_to_send_formatted[i : i + MAX_LEN]
                try:
                    # Use HTML parse mode as we escaped the summary
                    # Reply to the original message instead of just sending
                    await message.reply_text(chunk, parse_mode=ParseMode.HTML)
                    logger.info(f"Sent chunk {i // MAX_LEN + 1} successfully.")
                except Exception as send_err:
                    logger.error(
                        f"Failed to send chunk with HTML formatting: {send_err}. Trying plain text."
                    )
                    # Fallback to sending raw chunk without formatting if HTML fails
                    raw_chunk = text_to_send_raw[i : i + MAX_LEN]
                    try:
                        # Reply to the original message instead of just sending
                        await message.reply_text(raw_chunk)
                        logger.info(
                            f"Sent chunk {i // MAX_LEN + 1} successfully (plain text fallback)."
                        )
                    except Exception as plain_send_err:
                        logger.error(
                            f"Failed to send chunk even as plain text: {plain_send_err}"
                        )
                        # Stop sending chunks if even plain text fails for one
                        break

                if i + MAX_LEN < len(text_to_send_formatted):
                    await asyncio.sleep(0.5)  # Small delay between chunks

        # --- Silent Failure Cases ---
        elif isinstance(agent_result, str) and agent_result.startswith("Error:"):
            # Agent returned an error string
            logger.error(
                f"Agent failed for {extracted_url}. Error: {agent_result}. Not replying."
            )
            # Do nothing in the chat

        else:
            # Agent returned None or unexpected type
            if agent_result is None:
                logger.error(f"Agent returned None for {extracted_url}. Not replying.")
            else:
                logger.error(
                    f"Agent returned unexpected result type for {extracted_url}: {type(agent_result)}. Not replying."
                )
            # Do nothing in the chat

    except Exception as e:
        # --- Main Execution Error ---
        # Log the error but do not send anything to the user
        logger.error(
            f"Unhandled exception processing message for URL {extracted_url}: {e}",
            exc_info=True,
        )
        # Removed user-facing error reporting

    # Removed the finally block as the thinking_message is gone


# --- FastAPI Lifespan Management (Setup/Teardown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Application startup...")
    global ptb_app  # Make sure we're modifying the global instance

    # Check if we should run in polling mode
    # This needs to be checked early, before webhook or polling setup.
    should_use_polling = os.getenv("USE_POLLING", "false").lower() == "true"

    # Initialize the application first
    logger.info("Initializing PTB application...")
    await ptb_app.initialize()

    # Add handlers
    url_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    ptb_app.add_handler(url_handler)

    if should_use_polling:
        logger.info("Polling mode is active. Skipping webhook setup.")
        # For polling, PTB's run_polling() is typically called directly,
        # not within the FastAPI lifespan for Uvicorn.
        # However, if Uvicorn *is* used with polling, we ensure PTB is ready.
        # The actual polling loop will be started by the __main__ block if not using Uvicorn.
        # If using Uvicorn AND polling, the bot won't automatically start polling updates
        # unless we explicitly start a background task for it here.
        # For now, we assume if Uvicorn is running, webhook is preferred or manual polling start.
        # Let's log a warning if Uvicorn is running with polling enabled.
        if not os.getenv("_SUPERVISOR_USE_POLLING_MODE"):  # Flag to be set in __main__
            logger.warning(
                "Running with Uvicorn and USE_POLLING=true. "
                + "Polling will not start automatically by FastAPI. "
                + "Ensure polling is started by the main script execution if desired."
            )
        # We still need to start the application for handlers to be registered
        await ptb_app.start()  # Start the application components
        # await ptb_app.updater.start_polling() # This would start polling if needed here

    elif WEBHOOK_URL:  # Webhook mode
        full_webhook_url = (
            f"{WEBHOOK_URL.rstrip('/')}/{WEBHOOK_SECRET_PATH.lstrip('/')}"
        )
        logger.info(f"Setting webhook to: {full_webhook_url}")
        try:
            # The ptb_app.start() call below implicitly handles webhook registration
            # when a webhook URL is configured and it's not polling.
            # It calls `bot.set_webhook` internally.
            await ptb_app.start()
            # To be absolutely sure the webhook is set with parameters:
            # await ptb_app.bot.set_webhook(
            #     url=full_webhook_url,
            #     secret_token=os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN"),
            #     allowed_updates=Update.ALL_TYPES,
            # )
            logger.info("Webhook setup initiated by ptb_app.start().")
        except Exception as e:
            logger.error(
                f"Failed to set webhook via ptb_app.start(): {e}", exc_info=True
            )
            # Decide if you want to exit or continue without webhook
            # exit()
    else:  # No polling and no WEBHOOK_URL
        logger.warning(
            "USE_POLLING is false and WEBHOOK_URL not set. "
            + "Bot will not receive updates via webhook or polling."
        )
        # Still start the application for other potential uses (e.g. health checks)
        await ptb_app.start()

    # Create a flag to indicate the bot is initialized
    app.state.bot_initialized = True
    logger.info("Bot initialization complete.")

    yield

    # --- Shutdown ---
    logger.info("Application shutdown...")
    # Stop PTB application regardless of mode
    try:
        if should_use_polling:
            logger.info("Polling mode: Stopping PTB application...")
            # If polling was started by ptb_app.updater.start_polling()
            # await ptb_app.updater.stop()
        elif WEBHOOK_URL:
            logger.info("Webhook mode: Attempting to delete webhook...")
            await ptb_app.bot.delete_webhook()
            logger.info("Webhook deleted successfully.")

        await ptb_app.stop()
        await ptb_app.shutdown()
        logger.info("PTB Application stopped and shut down.")
    except Exception as e:
        logger.error(f"Error during PTB application shutdown: {e}", exc_info=True)


# --- FastAPI Application Definition ---
app = FastAPI(lifespan=lifespan)


# --- Webhook Endpoint ---
@app.post(f"/{WEBHOOK_SECRET_PATH}")
async def webhook(
    request: Request,
    secret_token: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Response:
    """Handles incoming Telegram updates via webhook."""
    logger.info("Webhook endpoint called")

    # --- Webhook Secret Token Verification ---
    TELEGRAM_WEBHOOK_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN")
    if TELEGRAM_WEBHOOK_SECRET_TOKEN and secret_token != TELEGRAM_WEBHOOK_SECRET_TOKEN:
        logger.warning(
            f"Invalid secret token received: '{secret_token}' vs expected token"
        )
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Ensure the bot is initialized before processing updates
    if not hasattr(app.state, "bot_initialized") or not app.state.bot_initialized:
        logger.error("Bot not yet initialized. Request rejected.")
        raise HTTPException(status_code=503, detail="Bot initialization in progress")

    try:
        # Get the raw request body for logging if needed
        body = await request.body()
        logger.info(f"Received webhook request body length: {len(body)} bytes")

        # Parse the request JSON
        update_data = await request.json()
        logger.info(f"Successfully parsed update JSON")

        # Convert to Telegram Update object
        update = Update.de_json(update_data, ptb_app.bot)
        logger.info(
            f"Received update: {update.update_id}, type: {type(update).__name__}"
        )

        # Extract some basic info for logging
        message = update.message or update.edited_message
        if message:
            logger.info(
                f"Message content: '{message.text if message.text else '[no text]'}'"
            )

        # Process the update
        # logger.info("Processing update with PTB application...")
        # await ptb_app.process_update(update)
        # logger.info(f"Successfully processed update {update.update_id}")

        # Kick off processing in the background and ACK Telegram immediately
        logger.info("Scheduling background processing...")
        asyncio.create_task(ptb_app.process_update(update))
        return {"ok": True}  # must be <10 s

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse webhook request JSON: {e}", exc_info=True)
        return {"ok": False, "error": "Invalid JSON"}
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        # Return 200 even on error to prevent Telegram from retrying too aggressively
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
        logger.info("Starting bot in polling mode (from __main__)...")
        # We need to initialize and add handlers if not done by FastAPI's lifespan
        # However, Application.builder().token() already creates ptb_app.
        # Ensure handlers are added before run_polling.

        # Temporarily set an environment variable to signal lifespan not to warn
        os.environ["_SUPERVISOR_USE_POLLING_MODE"] = "1"

        # Initialize PTB application, add handlers, and start components
        # This logic is now partly in lifespan, but run_polling needs a fully set up app.
        # The lifespan function will run if Uvicorn is *also* started, but for direct polling,
        # we need to ensure ptb_app is ready.

        async def main_polling():
            global ptb_app
            logger.info("Initializing PTB application for direct polling...")
            await ptb_app.initialize()
            url_handler = MessageHandler(
                filters.TEXT & (~filters.COMMAND), handle_message
            )
            ptb_app.add_handler(url_handler)
            await ptb_app.start()  # Start application components
            logger.info("Starting PTB polling loop...")
            await ptb_app.updater.start_polling(poll_interval=1.0)  # Start polling
            # Keep the event loop running for polling
            while True:
                await asyncio.sleep(3600)  # Keep alive, or use a more robust way

        try:
            asyncio.run(main_polling())
        except KeyboardInterrupt:
            logger.info("Polling stopped by user.")
        finally:
            # Cleanup if main_polling exits
            async def shutdown_polling():
                global ptb_app
                if ptb_app and ptb_app.updater.running:  # Check if updater is running
                    await ptb_app.updater.stop()
                if ptb_app and ptb_app.running:  # Check if app itself is running
                    await ptb_app.stop()
                if ptb_app:  # Ensure shutdown is called if app was initialized
                    await ptb_app.shutdown()
                logger.info("PTB application shut down after polling.")

            asyncio.run(shutdown_polling())
            if "_SUPERVISOR_USE_POLLING_MODE" in os.environ:
                del os.environ["_SUPERVISOR_USE_POLLING_MODE"]

    else:
        # Run in webhook mode with FastAPI/Uvicorn
        logger.info(f"Starting Uvicorn server on {host}:{port} for webhook mode...")
        uvicorn.run(app, host=host, port=port)
