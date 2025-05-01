import os
import re
from typing import Any, Dict, Tuple, TypedDict, Union

from baml_client import b
from baml_client.types import ContentType, Summary
from dotenv import load_dotenv
import tweepy

from langgraph.graph import StateGraph, END
from rich.console import Console
from tools.search import run_tavily_tool
from tools.pdf_handler import get_pdf_text
from tools.scrape import get_page_content_selenium, get_page_screenshot_selenium

load_dotenv()

console = Console()

# --- LangGraph Agent State ---


class AgentState(TypedDict):
    original_message: str
    url: str
    content_type: ContentType  # 'web' or 'pdf'
    content: str
    summary: str
    error: str | None
    screenshot_bytes: bytes | None
    fallback_content: str | None


# --- Define Graph Nodes ---


def init_state(state: AgentState) -> Dict[str, Any]:
    """Extracts the URL from the original message."""
    console.print("---INIT STATE---", style="yellow bold")
    message = state["original_message"]
    # Basic URL extraction (consider a more robust regex)
    url = next((word for word in message.split() if word.startswith("http")), None)
    if not url:
        return {"error": "No URL found in the message."}
    return {"url": url}


def route_content_type(state: AgentState) -> str:
    """Determines if the URL is a PDF, Twitter/X, or a webpage."""
    console.print("---ROUTING--- ", style="yellow bold")
    url = state["url"]
    if url.lower().endswith(".pdf"):
        console.print(f"Routing to PDF handler for: {url}", style="blue")
        return "pdf_extractor"
    elif re.search(r"https?://(www\.)?(twitter|x)\.com", url, re.IGNORECASE):
        console.print(f"Routing to Twitter extractor for URL: {url}", style="magenta")
        return "twitter_extractor"
    else:
        console.print(f"Routing to Web extractor for URL: {url}", style="magenta")
        return "web_extractor"


def get_web_content(state: AgentState) -> AgentState:
    """Fetches content from a standard webpage URL using Tavily extract."""
    console.print("---GET WEB CONTENT (Standard URL)---", style="yellow bold")
    url = state["url"]
    error_message = None
    content_source = ""
    content_type = ContentType.Webpage

    try:
        # Use Tavily extract for non-Twitter URLs
        console.print(f"Using Tavily extract for: {url}", style="cyan")
        extract_tool_results = run_tavily_tool(mode="extract", urls=[url])
        results_list = extract_tool_results.get("results", [])
        failed_results = extract_tool_results.get("failed_results", [])

        if results_list:
            for res in results_list:
                # Try to get 'raw_content' first, fallback to 'content'
                raw_content = res.get("raw_content")
                if not raw_content:
                    raw_content = res.get(
                        "content", ""
                    )  # Fallback if raw_content is missing

                if raw_content:  # Only add if content exists
                    content_source += f"URL: {res.get('url', 'N/A')}\n"
                    content_source += f"Raw Content: {raw_content}\n\n"
                # Optional: Include images if needed later
                # content_source += f"Images: {res.get('images', [])}\n"

        if failed_results:
            error_message = (
                f"Tavily failed to extract content from: {', '.join(failed_results)}"
            )
            console.print(error_message, style="red")
            # If extraction failed entirely and we have no content, set content_source empty
            if not content_source:
                content_source = ""

        # If after trying extract, we still have no content and no specific error, set a generic one
        if not content_source and not error_message:
            error_message = "Tavily extract did not return any content for the URL."
            console.print(error_message, style="red")

    except Exception as e:
        console.print(f"Error getting content from URL {url}: {e}", style="red bold")
        error_message = f"Error: An unexpected error occurred while getting content from the URL. {e}"
        content_source = ""  # Ensure content is empty on error

    return {
        "content_type": content_type,
        "content": content_source.strip(),  # Strip leading/trailing whitespace
        "error": error_message,
    }


def get_twitter_content(state: AgentState) -> AgentState:
    """Fetches content from a Twitter/X URL using tweepy."""
    console.print("---GET TWITTER/X CONTENT (tweepy)---", style="yellow bold")
    url = state["url"]
    error_message = None
    tweet_text = ""
    content_type = ContentType.Webpage  # Treat as webpage for summarization

    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        error_message = "Error: X_BEARER_TOKEN not found in environment variables."
        console.print(error_message, style="red bold")
        return {"content_type": content_type, "content": "", "error": error_message}

    try:
        # Extract tweet ID from URL
        match = re.search(r"/status/(\d+)", url)
        if not match:
            raise ValueError("Could not extract Tweet ID from URL")
        tweet_id = match.group(1)
        console.print(f"Extracted Tweet ID: {tweet_id}", style="cyan")

        client = tweepy.Client(bearer_token)
        console.print(f"Fetching tweet ID: {tweet_id} using tweepy", style="cyan")
        # Fetch tweet, requesting author ID and creation time as well
        # You might need 'expansions': 'author_id' and 'tweet.fields': 'created_at' for more context
        response = client.get_tweet(
            tweet_id, tweet_fields=["created_at", "public_metrics", "author_id"]
        )

        if response.data:
            tweet = response.data
            # Fetch user details for the author ID
            user_response = client.get_user(id=tweet.author_id)
            username = (
                user_response.data.username if user_response.data else "unknown_user"
            )
            tweet_text = f"@{username} ({tweet.created_at}): {tweet.text}"
            console.print(f"Successfully fetched tweet: {tweet.id}")
        else:
            # Handle cases where the tweet might be deleted, private, or ID invalid
            error_detail = "Unknown reason."
            if response.errors:
                error_detail = "; ".join(
                    [e.get("detail", str(e)) for e in response.errors]
                )
            error_message = f"Tweepy could not find or access tweet ID: {tweet_id}. Reason: {error_detail}"
            console.print(error_message, style="red")

    except tweepy.errors.TweepyException as e:
        console.print(f"Tweepy API error for URL {url}: {e}", style="red bold")
        error_message = f"Error: A Tweepy API error occurred: {e}"
    except ValueError as e:  # Catch the ID extraction error
        console.print(f"Error processing Twitter URL {url}: {e}", style="red bold")
        error_message = f"Error: {e}"
    except Exception as e:
        console.print(
            f"Unexpected error getting content from Twitter/X URL {url} using tweepy: {e}",
            style="red bold",
        )
        error_message = f"Error: An unexpected error occurred while getting Twitter/X content via tweepy. {e}"

    return {
        "content_type": content_type,
        "content": tweet_text.strip(),
        "error": error_message,
    }


def handle_pdf_content(state: AgentState) -> AgentState:
    """Downloads and extracts text from a PDF URL."""
    console.print("---HANDLE PDF CONTENT---", style="bold yellow")
    url = state["url"]
    error_message = None
    pdf_text = ""
    try:
        extracted_text = get_pdf_text(url)
        if extracted_text.startswith("Error:"):
            console.print(
                f"Error getting PDF content: {extracted_text}", style="red bold"
            )
            error_message = extracted_text
        else:
            console.print(
                f"Successfully extracted text from PDF: {url}", style="magenta"
            )
            pdf_text = extracted_text

    except Exception as e:
        console.print(f"Unexpected error handling PDF {url}: {e}", style="red bold")
        error_message = (
            f"Error: An unexpected error occurred while processing the PDF. {e}"
        )

    return {
        "content": pdf_text,
        "content_type": ContentType.PDF,
        "error": error_message,
    }


def fallback_scrape(state: AgentState) -> AgentState:
    """Attempts to get page content and a screenshot using Selenium as a fallback."""
    initial_error = state.get("error", "No specific error before fallback")
    console.print(f"---FALLBACK SCRAPE ({initial_error})---", style="bold red")
    url = state["url"]

    # Clear previous error before attempting fallback
    state["error"] = None  # Clear error before attempting fallback
    screenshot_bytes = None
    fallback_content = None
    fallback_error = None

    # Attempt to get page content using Selenium
    try:
        console.print(f"Attempting Selenium content scrape for: {url}", style="yellow")
        content_result = get_page_content_selenium(url)

        # The function now always returns a string - either content or error message
        if content_result and not content_result.startswith("Error:"):
            fallback_content = content_result
            console.print(
                f"Successfully scraped content with Selenium for: {url}", style="green"
            )
        else:
            # It's an error message from the tool
            fallback_error = (
                content_result
                if content_result
                else "Selenium content scrape failed without specific error"
            )
            console.print(fallback_error, style="red")

    except Exception as e_content:
        err_msg = (
            f"Unexpected error during Selenium content scrape for {url}: {e_content}"
        )
        console.print(err_msg, style="red bold")
        # Append to existing error or set if none exists
        fallback_error = f"{fallback_error}\n{err_msg}" if fallback_error else err_msg

    # Attempt to get screenshot using Selenium (regardless of content success/failure)
    try:
        console.print(f"Attempting Selenium screenshot for: {url}", style="yellow")
        screenshot_result = get_page_screenshot_selenium(url)

        # Check if we got bytes (success) or a string (error message)
        if isinstance(screenshot_result, bytes):
            screenshot_bytes = screenshot_result
            console.print(
                f"Successfully took screenshot with Selenium for: {url}", style="green"
            )
        elif isinstance(screenshot_result, str):
            # It's an error message from the tool
            screenshot_error = screenshot_result
            console.print(screenshot_error, style="red")
            # Append to existing error or set if none exists
            fallback_error = (
                f"{fallback_error}\n{screenshot_error}"
                if fallback_error
                else screenshot_error
            )
        else:
            # Unexpected return type
            screenshot_error = "Selenium screenshot returned unexpected type."
            console.print(screenshot_error, style="red")
            fallback_error = (
                f"{fallback_error}\n{screenshot_error}"
                if fallback_error
                else screenshot_error
            )

    except Exception as e_screenshot:
        err_msg = (
            f"Unexpected error during Selenium screenshot for {url}: {e_screenshot}"
        )
        console.print(err_msg, style="red bold")
        fallback_error = f"{fallback_error}\n{err_msg}" if fallback_error else err_msg

    # Log the results for debugging
    console.print(
        f"Fallback results: Screenshot: {'Yes' if screenshot_bytes else 'No'}, Content: {'Yes' if fallback_content else 'No'}",
        style="cyan",
    )

    # Update state with results and any errors encountered during fallback
    return {
        "screenshot_bytes": screenshot_bytes,
        "fallback_content": fallback_content,
        "error": fallback_error,  # This will contain errors from both attempts if they occurred
    }


def summarize_content(state: AgentState) -> AgentState:
    """Summarizes the extracted content using BAML, preserving screenshot state."""
    print(
        f"--- Debug: summarize_content received state: { {k: (type(v), len(v) if isinstance(v, (str, bytes)) else v) for k, v in state.items()} } ---"
    )
    console.print("---SUMMARIZE CONTENT---", style="bold green")

    content_to_summarize = state.get("content")
    source = "primary content"

    if not content_to_summarize:
        content_to_summarize = state.get("fallback_content")
        source = "fallback content"

    if not content_to_summarize:
        print(
            "--- Debug: No content found for summarization. Preserving screenshot state. ---"
        )
        console.print("No content available to summarize.", style="yellow")
        # Preserve screenshot, update error
        return {
            "summary": "",
            "error": state.get("error") or "No content found to summarize.",
            "screenshot_bytes": state.get("screenshot_bytes"),  # Preserve screenshot
            # No need to explicitly preserve fallback_content here if it wasn't found
        }

    print(f"--- Debug: Summarizing {len(content_to_summarize)} chars from {source} ---")

    url = state.get("url", "Unknown URL")
    try:
        # Use get with default for content_type just in case
        summary_result: Summary = b.SummarizeContent(
            content=content_to_summarize,  # Use the content we selected above
            content_type=state["content_type"],
            context=state["original_message"],
        )
        console.print(
            f"Successfully generated summary from {source}.", style="bold green"
        )
        title = getattr(summary_result, "title", "Error")
        points = getattr(summary_result, "key_points", [])
        summary = getattr(
            summary_result,
            "concise_summary",
            "Summarization service returned an unexpected response format.",
        )

        formatted_summary = f"# {title}\n\n"
        formatted_summary += "## Key Points:\n"
        for point in points:
            formatted_summary += f"- {point.strip()}\n"
        formatted_summary += f"\n## Summary:\n{summary.strip()}"
        formatted_summary = re.sub(r"\n\s*\n", "\n\n", formatted_summary).strip()

        # SUCCESS CASE: Return summary and preserve screenshot ONLY
        return {
            "summary": formatted_summary,
            "error": None,
            "screenshot_bytes": state.get("screenshot_bytes"),  # Preserve screenshot
            # Don't need fallback_content if summary succeeded
        }

    except Exception as e:
        console.print(f"Error during summarization for {url}: {e}", style="red bold")
        print(f"--- Debug: BAML summarization error: {e} ---")
        # FAILURE CASE: Return error, preserve screenshot AND fallback content
        return {
            "summary": "",
            "error": f"Summarization failed: {e}",
            "screenshot_bytes": state.get("screenshot_bytes"),  # Preserve screenshot
            "fallback_content": state.get(
                "fallback_content"
            ),  # Preserve fallback because summary failed
        }


# --- Conditional Edges Logic ---


def route_content_extraction(state: AgentState) -> str:
    """Determines the content extraction route."""
    console.print("---ROUTING--- ", style="yellow bold")
    url = state["url"]
    if url.lower().endswith(".pdf"):
        console.print(f"Routing to PDF handler for: {url}", style="blue")
        return "pdf_extractor"
    elif re.search(r"https?://(www\.)?(twitter|x)\.com", url, re.IGNORECASE):
        console.print(f"Routing to Twitter extractor for URL: {url}", style="magenta")
        return "twitter_extractor"
    else:
        console.print(f"Routing to Web extractor for URL: {url}", style="magenta")
        return "web_extractor"


def should_fallback(state: AgentState) -> str:
    """Determines whether to proceed to summarization or fallback to scraping."""
    print(
        f"--- Debug: should_fallback received state: { {k: (type(v), len(v) if isinstance(v, (str, bytes)) else v) for k, v in state.items()} } ---"
    )
    if state.get("error") or not state.get("content"):
        console.print("Routing: Condition met for Fallback Scrape.", style="yellow")
        return "fallback_scrape"
    else:
        console.print("Routing: Condition met for Summarization.", style="green")
        return "summarize_content"


def should_summarize_fallback(state: AgentState) -> str:
    """Determines routing after fallback: summarize text, end with screenshot, or end on failure."""
    print(
        f"--- Debug: should_summarize_fallback received state: { {k: (type(v), len(v) if isinstance(v, (str, bytes)) else v) for k, v in state.items()} } ---"
    )

    # Check if we have fallback content to summarize
    if state.get("fallback_content"):
        # If we have fallback content, use it for summarization
        console.print(
            "Routing: Fallback provided text, routing to Summarization.", style="green"
        )
        return "summarize_content"

    # If we only have a screenshot but no content, go to END
    # The run_agent function will handle returning the screenshot
    elif state.get("screenshot_bytes"):
        console.print(
            "Routing: Fallback provided only screenshot, routing to END.",
            style="magenta",
        )
        return END

    # Fallback failed completely
    else:
        console.print("Routing: Fallback failed, routing to END.", style="red")
        return END


# --- Build the Graph ---


def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("init", init_state)
    workflow.add_node("web_extractor", get_web_content)
    workflow.add_node("pdf_extractor", handle_pdf_content)
    workflow.add_node("twitter_extractor", get_twitter_content)
    workflow.add_node("fallback_scrape", fallback_scrape)
    workflow.add_node("summarize_content", summarize_content)

    # Define edges
    workflow.set_entry_point("init")

    # Route from identifier to the correct extractor
    workflow.add_conditional_edges(
        "init",
        route_content_extraction,
        {
            "web_extractor": "web_extractor",
            "pdf_extractor": "pdf_extractor",
            "twitter_extractor": "twitter_extractor",
            END: END,  # If routing fails (e.g., no URL found in init)
        },
    )

    # Route from primary extractors: fallback or summarize
    workflow.add_conditional_edges(
        "web_extractor",
        should_fallback,
        {
            "summarize_content": "summarize_content",
            "fallback_scrape": "fallback_scrape",
        },
    )
    workflow.add_conditional_edges(
        "pdf_extractor",
        should_fallback,
        {
            "summarize_content": "summarize_content",
            "fallback_scrape": "fallback_scrape",
        },
    )
    workflow.add_conditional_edges(
        "twitter_extractor",
        should_fallback,
        {
            "summarize_content": "summarize_content",
            "fallback_scrape": "fallback_scrape",
        },
    )

    # Route from fallback scrape: summarize text or end
    workflow.add_conditional_edges(
        "fallback_scrape",
        should_summarize_fallback,
        {"summarize_content": "summarize_content", END: END},
    )

    # Summarizer always goes to end
    workflow.add_edge("summarize_content", END)

    return workflow.compile()


graph = build_graph()

# --- Main Agent Function ---


async def run_agent(message: str) -> Union[str, Tuple[bytes, str | None], None]:
    """
    Runs the LangGraph agent workflow.

    Args:
        message: The original message containing the URL.

    Returns:
        - Tuple[bytes, str]: Screenshot bytes and summary text when both are available.
        - Tuple[bytes, str | None]: Screenshot bytes and optional fallback text if fallback scrape ran.
          The text part can be None if content scraping failed but screenshot succeeded.
        - str: Summary text on successful text extraction and summarization (when no screenshot is available).
        - str: An error message string if a significant error occurred preventing any output.
        - None: If all attempts (extraction, summarization, fallback) fail and no screenshot is available.
    """
    inputs = {"original_message": message}
    final_state = None
    try:
        # Use graph.ainvoke for async execution if needed, otherwise graph.invoke
        async for output in graph.astream(inputs, {"recursion_limit": 10}):
            # stream() yields dictionaries with node names as keys
            for key, value in output.items():
                console.print(f"Output from node '{key}':", style="cyan")
                # console.print(value) # Optional: Print the full state after each node
                final_state = value  # Keep track of the latest state

        if final_state:
            # Debug: Print the final state to see what we have
            console.print("FINAL STATE KEYS:", style="bold magenta")
            for key, value in final_state.items():
                if isinstance(value, bytes):
                    console.print(
                        f"  {key}: <bytes> ({len(value)} bytes)", style="magenta"
                    )
                elif isinstance(value, str) and len(value) > 100:
                    console.print(
                        f"  {key}: <string> ({len(value)} chars)", style="magenta"
                    )
                else:
                    console.print(f"  {key}: {value}", style="magenta")

            # Check if we have a screenshot (either from fallback or taken separately)
            screenshot_bytes = final_state.get("screenshot_bytes")
            if screenshot_bytes:
                console.print(
                    f"Screenshot available: {len(screenshot_bytes)} bytes",
                    style="bold green",
                )
            else:
                console.print("No screenshot available", style="bold yellow")

            # 1. Successful Summary
            if final_state.get("summary"):
                summary_text = final_state["summary"]
                console.print("---AGENT FINISHED: Summary---", style="bold green")

                # If we have both screenshot and summary, return both
                if screenshot_bytes:
                    console.print(
                        "---AGENT FINISHED: Summary + Screenshot---", style="bold green"
                    )
                    console.print(
                        f"Returning tuple: (screenshot_bytes[{len(screenshot_bytes)} bytes], summary_text[{len(summary_text)} chars])",
                        style="bold green",
                    )
                    return (
                        screenshot_bytes,
                        summary_text,
                    )  # Return both screenshot and summary
                else:
                    # Otherwise just return the summary
                    console.print(
                        f"Returning summary_text only: {len(summary_text)} chars",
                        style="bold green",
                    )
                    return summary_text

            # 2. Fallback Scrape Occurred
            elif (
                screenshot_bytes is not None
                or final_state.get("fallback_content") is not None
            ):
                content = final_state.get("fallback_content")
                # Prioritize returning screenshot if available
                if screenshot_bytes:
                    console.print(
                        "---AGENT FINISHED: Fallback Screenshot (and maybe Content)---",
                        style="bold yellow",
                    )
                    console.print(
                        f"Returning tuple: (screenshot_bytes[{len(screenshot_bytes)} bytes], content[{len(content) if content else 0} chars])",
                        style="bold yellow",
                    )
                    return (
                        screenshot_bytes,
                        content,
                    )  # Return tuple (bytes, str or None)
                # If only fallback content exists (screenshot failed but content didn't)
                elif content:
                    console.print(
                        "---AGENT FINISHED: Fallback Content Only---",
                        style="bold yellow",
                    )
                    # Decide how to handle this - maybe summarize fallback content?
                    # For now, return it directly as text. Bot needs to handle this.
                    # Consider adding a summarization step for fallback_content later.
                    console.print(
                        f"Returning fallback content only: {len(content)} chars",
                        style="bold yellow",
                    )
                    return "Fallback Content:\n" + content  # Return as string
                else:  # Fallback ran but failed for both screenshot and content
                    console.print(
                        "---AGENT FINISHED: Fallback Failed Completely---",
                        style="bold red",
                    )
                    error_msg = final_state.get(
                        "error", "Fallback failed without specific error."
                    )
                    console.print(
                        f"Returning error message: {error_msg}", style="bold red"
                    )
                    return (
                        "Error: Failed to process the URL even with fallback. Details: "
                        + error_msg
                    )

            # 3. Initial Extraction/Routing Error (before fallback)
            elif final_state.get("error"):
                console.print(
                    "---AGENT FINISHED: Error (Before Fallback)---", style="bold red"
                )
                console.print(
                    f"Returning error message: {final_state['error']}", style="bold red"
                )
                return "Error: " + final_state["error"]

            # 4. Unexpected scenario
            else:
                console.print("---AGENT FINISHED: Unknown State---", style="bold red")
                console.print("Returning generic error message", style="bold red")
                return "Error: Agent finished in an unexpected state."

        else:
            console.print("---AGENT FAILED: No Final State---", style="bold red")
            console.print("Returning error about no final state", style="bold red")
            return "Error: Agent workflow did not produce a final state."

    except Exception as e:
        console.print("---AGENT FAILED: Runtime Exception---", style="bold red")
        console.print_exception(show_locals=True)
        console.print(f"Returning error message: {str(e)}", style="bold red")
        return "Error: An unexpected error occurred in the agent: " + str(e)


# Example usage (for testing)
if __name__ == "__main__":
    url = "https://www.darioamodei.com/post/the-urgency-of-interpretability"
    result = run_agent(url=url)
    console.print(result, style="bold")
