# bot.py

import logging
import re
import html # For escaping HTML in messages
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import the agent runner and config
from agent import run_agent
from config import TELEGRAM_BOT_TOKEN

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Constants ---
# Simple regex to find the first URL in a message
URL_REGEX = r'https?://\S+'

# --- Message Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages, extracts URLs, and triggers the summarizer agent."""
    message = update.message
    chat_id = message.chat_id
    text = message.text

    if not text:
        return

    # Find the first URL in the message
    match = re.search(URL_REGEX, text)
    if not match:
        # logger.debug("No URL found in message.")
        return # Ignore messages without URLs

    url = match.group(0)
    logger.info(f"URL detected in chat {chat_id}: {url}")

    # Send a typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    # Pass the original message text to the agent, as it might contain context/query
    # Or just pass the URL if the agent's start_node is designed for that
    # Current agent.run_agent expects the full message text
    try:
        # Use asyncio.create_task to run the agent concurrently if needed,
        # but for now, let's run it directly and wait.
        summary_or_error = await run_agent(text) # Pass the full message text

        # Escape HTML characters in the result to prevent formatting issues
        escaped_result = html.escape(summary_or_error)

        # Send the result back
        # Consider using message threads if available/appropriate
        await message.reply_text(escaped_result, parse_mode=ParseMode.HTML)
        logger.info(f"Sent summary/error back to chat {chat_id}")

    except Exception as e:
        logger.error(f"Error handling message for chat {chat_id}: {e}", exc_info=True)
        await message.reply_text(f"Sorry, an unexpected error occurred while processing the link: {html.escape(str(e))}", parse_mode=ParseMode.HTML)

# --- Main Function ---
def main() -> None:
    """Starts the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
        return

    logger.info("Starting Telegram bot...")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register the handler for text messages in private chats and groups/supergroups
    # Using filters.TEXT & (~filters.COMMAND) to avoid capturing commands
    url_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(url_handler)

    # Start the Bot
    logger.info("Bot polling started.")
    application.run_polling()

if __name__ == '__main__':
    main()
