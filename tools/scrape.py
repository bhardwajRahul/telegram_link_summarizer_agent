import os
import asyncio
# import nest_asyncio

# Apply nest_asyncio - useful if running within an environment that already has an event loop (like Jupyter)
# May not be strictly necessary in all execution contexts, but safe to include based on example.
# nest_asyncio.apply()

# Import the necessary components from crawl4ai
from crawl4ai import AsyncWebCrawler, CacheMode, BrowserConfig, CrawlerRunConfig

# Define a default configuration (optional, customize as needed)
default_crawler_config = CrawlerRunConfig(
    cache_mode=CacheMode.ENABLED  # Or BYPASS, REFRESH, etc.
    # Add other config options here if needed, e.g.:
    # browser_config=BrowserConfig(headless=True)
)


async def get_content_with_crawl4ai(url: str, timeout: int = 120) -> str:
    """Fetches content from a URL asynchronously using the crawl4ai library.

    Args:
        url: The URL of the webpage to scrape.
        timeout: Maximum time in seconds to wait for the crawl operation.
                 Note: Timeout might be part of CrawlerRunConfig or AsyncWebCrawler instantiation.
                 The provided example doesn't explicitly show timeout handling in arun.
                 Consult crawl4ai docs for precise timeout control with async.

    Returns:
        str: The extracted text content (likely Markdown v2) or an error message string.
    """
    print(f"Attempting fallback content extraction for {url} using AsyncWebCrawler")

    try:
        # Instantiate the AsyncWebCrawler using async with for proper resource management
        async with AsyncWebCrawler() as crawler:
            # Run the crawler asynchronously for the single URL
            # Pass the configuration object
            # TODO: Verify how timeout is handled in async version (might be in config or crawler init)
            result = await crawler.arun(
                url=url,
                config=default_crawler_config,  # Use the defined config
            )

            # Process the result
            if result and result.status == "success":
                # Access the extracted content - using markdown_v2 based on example
                content = getattr(result, "markdown_v2", None)
                # Fallback to older attribute names if needed
                if content is None:
                    content = getattr(result, "markdown", getattr(result, "data", None))

                # The content object might have further attributes like raw_markdown
                final_markdown = ""
                if hasattr(content, "raw_markdown"):
                    final_markdown = content.raw_markdown
                elif isinstance(content, str):  # Handle if it directly returns a string
                    final_markdown = content

                if final_markdown:
                    print(
                        f"SUCCESS: Extracted content using crawl4ai library ({len(final_markdown)} chars)."
                    )
                    return final_markdown
                else:
                    error_msg = f"Error: crawl4ai library succeeded for {url} but returned no markdown_v2 content."
                    print(error_msg)
                    return error_msg
            elif result:
                # Handle crawler failure status
                error_msg = f"Error: crawl4ai library failed for {url}. Status: {result.status}, Message: {getattr(result, 'error', 'N/A')}"
                print(error_msg)
                return error_msg
            else:
                # Handle cases where crawler.arun() returns None or unexpected value
                error_msg = f"Error: crawl4ai library returned an unexpected result (None?) for {url}."
                print(error_msg)
                return error_msg

    except ImportError:
        error_msg = "Error: crawl4ai library is not installed. Please add it to your requirements."
        print(error_msg)
        return error_msg
    except Exception as e:
        # Catch potential errors during Crawler instantiation or run
        error_msg = f"Error: An unexpected error occurred during AsyncWebCrawler execution for {url}: {e}"
        print(error_msg)
        # Consider logging the traceback here for debugging
        import traceback

        traceback.print_exc()
        return error_msg


if __name__ == "__main__":

    async def main_test():
        # Simple test - replace with a URL you expect crawl4ai to handle
        # test_url = "https://x.com/Nils_Reimers/status/1915431608980586874" # Example Twitter/X URL
        test_url = "https://blog.langchain.dev/introducing-langgraph-cloud/"  # Example Blog Post
        print(f"Testing crawl4ai async library scraping for URL: {test_url}")

        # Ensure crawl4ai is installed in the environment
        content = await get_content_with_crawl4ai(test_url)

        if content and not content.startswith("Error:"):
            print(
                f"\nSuccessfully retrieved content (first 500 chars):\n{content[:500]}"
            )
        else:
            print(f"\nFailed to retrieve content or an error occurred:\n{content}")

    # Run the async main function
    asyncio.run(main_test())
