import logging
import io
import re
from urllib.parse import urlparse

import requests
from firecrawl import FirecrawlApp
from bs4 import BeautifulSoup
from pypdf import PdfReader

from config import FIRECRAWL_API_KEY

logger = logging.getLogger(__name__)

# --- Firecrawl Client Initialization ---
firecrawl_client = None
if FIRECRAWL_API_KEY:
    try:
        firecrawl_client = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        logger.info("Firecrawl client initialized in tools/scrape.py.")
    except Exception as e:
        logger.error(f"Failed to initialize Firecrawl client: {e}", exc_info=True)
else:
    logger.warning("FIRECRAWL_API_KEY not found. Firecrawl tool disabled.")


def is_pdf_url(url: str) -> bool:
    """Checks if a URL likely points to a PDF."""
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    if path.endswith(".pdf"):
        return True
    try:
        # Use HEAD request for efficiency
        response = requests.head(url, timeout=10, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/pdf" in content_type:
            return True
    except requests.RequestException as e:
        logger.warning(f"Could not check HEAD for {url}: {e}")
        # As a fallback, we might still try PDF extraction later if needed
    return False


def extract_text_from_pdf(url: str) -> str:
    """Downloads a PDF from a URL and extracts text using pypdf."""
    logger.info(f"Attempting to extract text from PDF: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        # Double-check content type even if HEAD failed or wasn't PDF
        if "application/pdf" not in content_type:
            logger.warning(f"URL {url} did not return PDF content type, got {content_type}. Attempting extraction anyway.")

        reader = PdfReader(io.BytesIO(response.content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text:
            logger.warning(f"No text extracted from PDF: {url}")
            return "Error: Could not extract text from PDF."

        logger.info(f"Successfully extracted text from PDF: {url} (Length: {len(text)}) ")
        return text.strip()

    except requests.RequestException as e:
        logger.error(f"Failed to download PDF from {url}: {e}", exc_info=True)
        return f"Error: Could not download PDF from URL. {e}"
    except Exception as e:
        logger.error(f"Failed to process PDF content from {url}: {e}", exc_info=True)
        return f"Error: Could not process PDF content. {e}"


def firecrawl_scrape(url: str) -> str:
    """Uses Firecrawl to scrape a URL, extracting markdown or cleaned text."""
    if not firecrawl_client:
        logger.error("Firecrawl client not initialized. Cannot scrape.")
        return "Error: Firecrawl client not available. Check API Key."
    logger.info(f"Attempting Firecrawl scrape for URL: {url}")
    try:
        # Prioritize getting markdown content
        scraped_data = firecrawl_client.scrape_url(url, {'pageOptions': {'onlyMainContent': True}})

        if scraped_data and 'markdown' in scraped_data and scraped_data['markdown']:
            logger.info(f"Firecrawl scrape successful (markdown) for {url} (Length: {len(scraped_data['markdown'])})")
            return scraped_data['markdown']
        elif scraped_data and 'content' in scraped_data and scraped_data['content']:
            # Fallback to cleaning raw HTML content if markdown isn't available
            logger.warning(f"Firecrawl returned content but no markdown for {url}. Using raw content.")
            soup = BeautifulSoup(scraped_data['content'], "html.parser")
            # Remove script and style elements
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            # Get text, separating blocks by newlines and stripping extra whitespace
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n\s*\n", "\n\n", text).strip() # Clean up multiple newlines
            if text:
                logger.info(f"Firecrawl raw content extraction for {url} (Length: {len(text)}) ")
                return text
            else:
                 logger.error(f"Firecrawl scrape failed for {url}: No markdown or usable raw content found.")
                 return "Error: Firecrawl failed to extract meaningful content."
        else:
            logger.error(f"Firecrawl scrape failed for {url}: Empty or unexpected response format.")
            return "Error: Firecrawl returned no usable content."

    except Exception as e:
        logger.error(f"Firecrawl scrape failed for {url}: {e}", exc_info=True)
        return f"Error: Firecrawl encountered an error during scraping. {e}"
