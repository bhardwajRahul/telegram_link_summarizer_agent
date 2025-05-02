import os
from rich.console import Console

from tools.search import run_tavily_tool

console = Console()


def scrape_linkedin_post(url: str) -> dict | str:
    """
    Uses the generic Tavily tool runner to extract content specifically from a LinkedIn URL.

    Args:
        url: The LinkedIn post URL.

    Returns:
        A dictionary containing the extracted content and source URL, or an error string.
    """
    if "linkedin.com/posts/" not in url:
        return "Error: URL does not appear to be a valid LinkedIn post URL."

    console.print(
        f"Attempting to extract content from LinkedIn URL via run_tavily_tool: {url}",
        style="blue",
    )

    # Define the specific parameters for LinkedIn search via Tavily
    tavily_params = {
        "search_depth": "advanced",
        "max_results": 1,
        # "include_raw_content": True,
    }

    try:
        # Call the generic Tavily tool runner
        results = run_tavily_tool(mode="search", query=url, **tavily_params)

        # --- Result Parsing (similar to before) ---

        # Handle error strings returned by run_tavily_tool
        if isinstance(results, str) and results.startswith("Error:"):
            console.print(
                f"run_tavily_tool reported an error: {results}", style="bold red"
            )
            return results  # Propagate the error

        # Handle unexpected return types
        if not isinstance(results, dict):
            console.print(
                f"run_tavily_tool returned unexpected type: {type(results)}",
                style="bold red",
            )
            return "Error: Unexpected response format from Tavily tool."

        # Check if the dictionary contains results
        if not results.get("results"):
            console.print(
                f"Tavily search (via run_tavily_tool) returned no results for the URL.",
                style="bold yellow",
            )
            return "Error: Tavily found no information for this LinkedIn URL."

        # Extract content from the first result
        first_result = results["results"][0]
        extracted_content = first_result.get("content")
        raw_content = first_result.get("raw_content")
        source_url = first_result.get("url")  # Get the source URL Tavily found

        if extracted_content:
            console.print("Extracted content found via run_tavily_tool.", style="green")
            return {"content": extracted_content, "source_url": source_url}
        elif raw_content:
            console.print("Raw content found via run_tavily_tool.", style="green")
            return {"content": raw_content, "source_url": source_url}
        else:
            console.print(
                "No 'content' or 'raw_content' found in Tavily results (via run_tavily_tool).",
                style="bold yellow",
            )
            return (
                "Error: Tavily returned results, but no extractable content was found."
            )

    except Exception as e:
        # Catch potential errors during the call or parsing
        console.print(
            f"Error processing LinkedIn URL with run_tavily_tool: {e}",
            style="bold red",
            exc_info=True,
        )
        return f"Error: Failed to process LinkedIn URL using Tavily tool. {e}"


# Example Usage (for testing)
if __name__ == "__main__":
    # Ensure tools.search can initialize its Tavily client (e.g., reads API key)
    test_url = "https://www.linkedin.com/posts/omarsar_llms-for-engineering-activity-7324064951734603776-Ravc?utm_source=share&utm_medium=member_desktop&rcm=ACoAABDFOm0BmXlu4cLYtJePo0mLzdFoB5itUNU"

    print(f"Testing LinkedIn scraper with URL: {test_url}")
    result = scrape_linkedin_post(test_url)
    print("\nResult:")
    if isinstance(result, dict):
        print(f"Source URL: {result.get('source_url')}")
        print("--- Content ---")
        print(result.get("content"))
        print("---------------")
    else:
        print(result)
