# tools/search.py

from tavily import TavilyClient  # type: ignore
import logging

from config import TAVILY_API_KEY

logger = logging.getLogger(__name__)


class TavilySearch:
    """Provides functionality to search the web using the Tavily API."""

    def __init__(self):
        self.client = None
        if TAVILY_API_KEY:
            try:
                self.client = TavilyClient(api_key=TAVILY_API_KEY)
                logger.info("TavilyClient initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize TavilyClient: {e}")
        else:
            logger.warning("Tavily API key not provided. Tavily search disabled.")

    def search(self, query: str, max_results: int = 3) -> tuple[str | None, str | None]:
        """
        Performs a web search using Tavily.

        Returns:
            tuple[str | None, str | None]: (search_results_string, error_message)
        """
        if not self.client:
            return (
                None,
                "Tavily client is not available (API key missing or initialization failed).",
            )

        try:
            logger.info(f"Performing Tavily search for query: '{query}'")
            # Using search, which includes context and relevance scoring
            response = self.client.search(
                query=query,
                search_depth="basic",  # 'basic' is often sufficient, 'advanced' is slower/costlier
                max_results=max_results,
                include_answer=False,  # We just want the source contexts for now
            )

            if not response or "results" not in response or not response["results"]:
                logger.warning(
                    f"Tavily search returned no results for query: '{query}'"
                )
                return "No search results found.", None

            # Format results for potential inclusion in LLM context
            results_str = "\n\n".join()
            logger.info(
                f"Successfully retrieved {len(response['results'])} results from Tavily."
            )
            return results_str, None

        except Exception as e:
            logger.error(
                f"Error during Tavily search for query '{query}': {e}", exc_info=True
            )
            return None, f"An error occurred during Tavily search: {e}"
