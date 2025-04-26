import sys
import os
from rich.console import Console
from tavily import TavilyClient

sys.path.append(os.getcwd())

from config import TAVILY_API_KEY

console = Console()

# --- Tavily Client Initialization ---
tavily_client = None
if TAVILY_API_KEY:
    try:
        # Initialize TavilyClient
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        console.print("Tavily client initialized in tools/search.py.", style="bold green")
    except Exception as e:
        console.print(f"Failed to initialize Tavily client: {e}", style="bold red", exc_info=True)
else:
    console.print("TAVILY_API_KEY not found in config. Tavily tool disabled.", style="bold yellow")

def run_tavily_tool(mode: str, query: str = None, urls: list[str] = None, **kwargs) -> dict | str:
    """
    Uses Tavily client to perform search or extract content from URLs.

    Args:
        mode: The operation mode ('search' or 'extract').
        query: The search query (required for 'search' mode).
        urls: A list of URLs to extract content from (required for 'extract' mode).
        **kwargs: Additional parameters for the Tavily API (e.g., max_results, topic, time_range for search).

    Returns:
        A dictionary containing the results (search or extract), or an error string.
    """
    if not tavily_client:
        console.print("Tavily client not initialized. Cannot perform operation.", style="bold red")
        return "Error: Tavily client is not available. Check API Key."

    try:
        if mode == 'search':
            if not query:
                return "Error: Query is required for search mode."
            results = tavily_client.search(query=query, **kwargs)
            console.print(f"Tavily search successful for query: '{query}'", style="green")

        elif mode == 'extract':
            if not urls:
                return "Error: URLs are required for extract mode."
            results = tavily_client.extract(urls=urls, **kwargs)
            console.print(f"Tavily extract successful for URLs: {urls}", style="green")

        else:
            return f"Error: Invalid mode '{mode}'. Use 'search' or 'extract'."

        if not results:
            console.print(f"Tavily {mode} returned no results.", style="bold yellow")
            return f"Error: Tavily {mode} found no information."

        # The SDK returns a dictionary directly
        return results

    except Exception as e:
        console.print(f"Tavily {mode} failed: {e}", style="bold red", exc_info=True)
        return f"Error: Tavily {mode} encountered an error. {e}"

# Example for testing (optional)
if __name__ == "__main__":
    # --- Test Search ---
    # test_query = "Find the recent blog post from Dario Amodei about AI Interpretability"
    # console.print(f"\n--- Testing Tavily Search for: '{test_query}' ---", style="bold blue")
    # search_results = run_tavily_tool(mode='search', query=test_query, topic="news", max_results=3)
    # console.print("Search results:", style="bold green")
    # console.print(search_results)
    # console.print("--- End Search Test ---", style="bold blue")

    # --- Test Extract --- 
    # Example URLs (replace with valid ones if needed)
    test_urls_for_extract = [
        "https://www.darioamodei.com/post/the-urgency-of-interpretability"
    ]
    console.print(f"\n--- Testing Tavily Extract for URLs: {test_urls_for_extract} ---", style="bold blue")
    extract_results = run_tavily_tool(mode='extract', urls=test_urls_for_extract)
    console.print("Extract results:", style="bold green")
    console.print(extract_results)
    console.print("--- End Extract Test ---", style="bold blue")
