# tools/scraper.py

import requests
import trafilatura
from trafilatura.settings import use_config
from firecrawl import FirecrawlApp  # type: ignore
import logging

from config import FIRECRAWL_API_KEY

logger = logging.getLogger(__name__)

# Configure trafilatura to be less aggressive initially
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "10")  # 10 second timeout


class WebScraper:
    """Handles fetching and extracting text content from web URLs."""

    def __init__(self):
        self.firecrawl_app = None
        if FIRECRAWL_API_KEY:
            try:
                self.firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
                logger.info("FirecrawlApp initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize FirecrawlApp: {e}")
                self.firecrawl_app = None
        else:
            logger.warning(
                "Firecrawl API key not provided. Firecrawl scraping disabled."
            )

    def _fetch_html(self, url: str) -> str | None:
        """Fetches HTML content from a URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            # Attempt to decode using apparent encoding, fallback to utf-8
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None

    def _extract_with_trafilatura(self, html_content: str, url: str) -> str | None:
        """Extracts main text content using Trafilatura."""
        try:
            # include_links=False to avoid summarizing link texts
            extracted_text = trafilatura.extract(
                html_content,
                url=url,
                include_comments=False,
                include_tables=True,
                include_links=False,
                favor_precision=True,  # Prioritize accuracy over recall
                config=config,
            )
            if (
                extracted_text and len(extracted_text) > 100
            ):  # Basic check for meaningful content
                logger.info(
                    f"Successfully extracted content using Trafilatura for {url}"
                )
                return extracted_text
            else:
                logger.warning(
                    f"Trafilatura extracted minimal (<100 chars) or no content for {url}."
                )
                return None
        except Exception as e:
            logger.error(f"Error during Trafilatura extraction for {url}: {e}")
            return None

    def _extract_with_firecrawl(self, url: str) -> str | None:
        """Extracts main text content using Firecrawl."""
        if not self.firecrawl_app:
            logger.warning(
                f"Firecrawl not available, skipping Firecrawl extraction for {url}."
            )
            return None
        try:
            logger.info(f"Attempting Firecrawl extraction for {url}...")
            # Use crawl for potentially deeper extraction than scrape
            crawl_result = self.firecrawl_app.crawl_url(
                url=url, params={"pageOptions": {"onlyMainContent": True}}
            )
            # Firecrawl crawl_url returns a list of documents, assume first is the main one
            if (
                crawl_result
                and isinstance(crawl_result, list)
                and "markdown" in crawl_result
            ):
                extracted_text = crawl_result["markdown"]
                if extracted_text and len(extracted_text) > 100:
                    logger.info(
                        f"Successfully extracted content using Firecrawl for {url}"
                    )
                    return extracted_text
                else:
                    logger.warning(
                        f"Firecrawl extracted minimal (<100 chars) or no content for {url}."
                    )
                    return None
            else:
                logger.warning(
                    f"Firecrawl did not return expected markdown content for {url}."
                )
                return None
        except Exception as e:
            logger.error(f"Error during Firecrawl extraction for {url}: {e}")
            return None

    def scrape_url(self, url: str) -> tuple[str | None, str | None]:
        """
        Scrapes a URL using a tiered approach: Trafilatura first, then Firecrawl.

        Returns:
            tuple[str | None, str | None]: (extracted_text, error_message)
        """
        logger.info(f"Starting scrape process for URL: {url}")

        # 1. Fetch HTML
        html_content = self._fetch_html(url)
        if not html_content:
            return None, f"Failed to fetch HTML content from {url}."

        # 2. Try Trafilatura
        extracted_text = self._extract_with_trafilatura(html_content, url)
        if extracted_text:
            return extracted_text, None  # Success with Trafilatura

        # 3. Try Firecrawl as fallback (if available and Trafilatura failed)
        logger.info(
            f"Trafilatura failed or yielded minimal content for {url}. Trying Firecrawl fallback."
        )
        extracted_text = self._extract_with_firecrawl(url)
        if extracted_text:
            return extracted_text, None  # Success with Firecrawl

        # 4. If both fail
        logger.error(
            f"Failed to extract meaningful content from {url} using all methods."
        )
        return (
            None,
            f"Failed to extract content from {url} after trying multiple methods.",
        )
