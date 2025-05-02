import os
import re
from typing import Any, Dict, TypedDict, Union

from baml_client import b
from baml_client.types import ContentType, Summary
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from rich.console import Console
from tools.search import run_tavily_tool
from tools.pdf_handler import get_pdf_text
from tools.twitter_api_tool import fetch_tweet_thread

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


# --- Define Graph Nodes ---


def init_state(state: AgentState) -> Dict[str, Any]:
    """Extracts the URL from the original message."""
    console.print("---INIT STATE---", style="yellow bold")
    message = state["original_message"]
    # Basic URL extraction (consider a more robust regex)
    url = next((word for word in message.split() if word.startswith("http")), None)
    if not url:
        return {"error": "No URL found in the message."}
    return {
        "original_message": message,
        "url": url,
        "content_type": ContentType.Webpage,
        "content": "",
        "summary": "",
        "error": None if url else "No URL found in the message.",
    }


def get_web_content(state: AgentState) -> AgentState:
    """Fetches content from a standard webpage URL using Tavily extract."""
    console.print("---GET WEB CONTENT (Tavily Extract)---", style="yellow bold")
    url = state["url"]
    error_message = None
    content_source = ""
    content_type = ContentType.Webpage

    # Reset error from previous steps if any
    state["error"] = None

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
        **state,
        "content_type": content_type,
        "content": content_source.strip(),  # Strip leading/trailing whitespace
        "error": error_message,
    }


def get_twitter_content(state: AgentState) -> AgentState:
    """Fetches content from a Twitter/X URL using twitter_api_tool."""
    console.print("---GET TWITTER/X CONTENT (twitterapi.io)---", style="yellow bold")
    url = state["url"]
    error_message = None
    content_result = ""
    content_type = ContentType.Webpage

    # Reset error from previous steps if any
    state["error"] = None

    try:
        console.print(f"Fetching tweet thread for URL: {url}", style="cyan")
        # Use the new tool
        content_result = fetch_tweet_thread(url)

        # Check if the tool returned an error message
        if content_result.startswith("Error:"):
            error_message = content_result
            console.print(error_message, style="red bold")
            content_result = ""  # Ensure content is empty if tool errored
        else:
            console.print(
                f"Successfully fetched Twitter content for: {url}", style="green"
            )

    except Exception as e:
        console.print(
            f"Unexpected error calling fetch_tweet_thread for {url}: {e}",
            style="red bold",
        )
        error_message = (
            f"Error: An unexpected error occurred while calling the Twitter tool. {e}"
        )
        content_result = ""

    return {
        **state,
        "content_type": content_type,
        "content": content_result.strip(),
        "error": error_message,
    }


def handle_pdf_content(state: AgentState) -> AgentState:
    """Downloads and extracts text from a PDF URL."""
    console.print("---HANDLE PDF CONTENT---", style="bold yellow")
    url = state["url"]
    error_message = None
    pdf_text = ""

    # Reset error from previous steps if any
    state["error"] = None

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
        **state,
        "content": pdf_text,
        "content_type": ContentType.PDF,
        "error": error_message,
    }


def summarize_content(state: AgentState) -> AgentState:
    """Summarizes the extracted content using BAML."""
    console.print("---SUMMARIZE CONTENT---", style="bold green")

    content_to_summarize = state.get("content")

    if not content_to_summarize or content_to_summarize.strip() == "":
        console.print("No content available to summarize.", style="yellow")
        # If we reached here due to an upstream error, preserve it
        # Otherwise, set an error indicating no content.
        final_error = state.get("error") or "No content found to summarize."
        return {
            **state,
            "summary": "",
            "error": final_error,
        }

    url = state.get("url", "Unknown URL")
    summarization_error = None
    formatted_summary = ""

    try:
        console.print(
            f"--- Debug: Summarizing {len(content_to_summarize)} chars ---", style="dim"
        )
        summary_result: Summary = b.SummarizeContent(
            content=content_to_summarize,
            content_type=state.get("content_type", ContentType.Webpage),
            context=state.get("original_message", ""),
        )
        console.print(f"Successfully generated summary.", style="bold green")
        title = getattr(summary_result, "title", "Summary")  # Default title
        points = getattr(summary_result, "key_points", [])
        summary_text = getattr(
            summary_result,
            "concise_summary",
            "Summarization service returned an unexpected response format.",
        )

        formatted_summary = f"# {title}\n\n"
        formatted_summary += "## Key Points:\n"
        for point in points:
            formatted_summary += f"- {point.strip()}\n"
        formatted_summary += f"\n## Summary:\n{summary_text.strip()}"
        formatted_summary = re.sub(r"\n\s*\n", "\n\n", formatted_summary).strip()

        # Clear any previous error if summarization succeeds
        summarization_error = None

    except Exception as e:
        console.print(f"Error during summarization for {url}: {e}", style="red bold")
        print(f"--- Debug: BAML summarization error: {e} ---")
        summarization_error = f"Summarization failed: {e}"
        formatted_summary = ""  # Ensure summary is empty on error

    return {
        **state,
        "summary": formatted_summary,
        "error": summarization_error,
    }


# --- Conditional Edges Logic ---


def route_content_extraction(state: AgentState) -> str:
    """Determines the content extraction route."""
    console.print("---ROUTING (Content Type)--- ", style="yellow bold")
    url = state["url"]
    if state.get("error"):
        console.print(
            f"Routing to END due to initialization error: {state['error']}", style="red"
        )
        return END
    if url.lower().endswith(".pdf"):
        console.print(f"Routing to PDF handler for: {url}", style="blue")
        return "pdf_extractor"
    elif re.search(r"https?://(www\.)?(twitter|x)\.com", url, re.IGNORECASE):
        console.print(f"Routing to Twitter extractor for URL: {url}", style="magenta")
        return "twitter_extractor"
    else:
        console.print(f"Routing to Web extractor for URL: {url}", style="magenta")
        return "web_extractor"


def should_summarize(state: AgentState) -> str:
    """Determines whether to proceed to summarization or end."""
    content = state.get("content")
    error = state.get("error")
    has_content = content and content.strip() != ""

    if error:
        console.print(
            f"Routing: Error occurred ('{error}'), routing to END.", style="red"
        )
        return END
    elif has_content:
        console.print(
            "Routing: Content extracted successfully, routing to Summarize.",
            style="green",
        )
        return "summarize_content"
    else:
        console.print(
            "Routing: No content extracted and no specific error, routing to END.",
            style="yellow",
        )
        # This case might indicate an issue in the extractor logic if it didn't set an error
        state["error"] = "Content extraction finished with no content and no error."
        return END


# --- Build the Graph ---


def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("init", init_state)
    workflow.add_node("web_extractor", get_web_content)
    workflow.add_node("pdf_extractor", handle_pdf_content)
    workflow.add_node("twitter_extractor", get_twitter_content)
    workflow.add_node("summarize_content", summarize_content)

    # Define edges
    workflow.set_entry_point("init")

    # Route directly from init using the conditional edge
    workflow.add_conditional_edges(
        "init",  # Edges now originate from init
        route_content_extraction,
        {
            "web_extractor": "web_extractor",
            "pdf_extractor": "pdf_extractor",
            "twitter_extractor": "twitter_extractor",
            END: END,  # Handle init errors
        },
    )

    # Route from each extractor to the summarization check
    workflow.add_conditional_edges(
        "web_extractor",
        should_summarize,
        {
            "summarize_content": "summarize_content",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "pdf_extractor",
        should_summarize,
        {
            "summarize_content": "summarize_content",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "twitter_extractor",
        should_summarize,
        {
            "summarize_content": "summarize_content",
            END: END,
        },
    )

    # Summarizer always goes to end
    workflow.add_edge("summarize_content", END)

    return workflow.compile()


graph = build_graph()

# --- Main Agent Function ---


async def run_agent(message: str) -> Union[str, None]:
    """
    Runs the LangGraph agent workflow for URL summarization.

    Args:
        message: The original message containing the URL.

    Returns:
        - str: Summary text on successful extraction and summarization.
        - str: An error message string if a significant error occurred.
        - None: Should ideally not be returned if error handling is robust.
    """
    inputs = {"original_message": message}
    final_state = None
    try:
        # Use graph.astream for async execution
        async for output in graph.astream(inputs, {"recursion_limit": 10}):
            for key, value in output.items():
                console.print(f"Output from node '{key}':", style="dim")
                final_state = value  # Keep track of the latest state

        if final_state:
            # Debug: Print the final state (simplified)
            console.print("---FINAL STATE---", style="bold magenta")
            for key, value in final_state.items():
                if key == "content" and isinstance(value, str) and len(value) > 200:
                    console.print(
                        f"  {key}: <string> ({len(value)} chars)", style="magenta"
                    )
                elif isinstance(value, str) and len(value) > 100:
                    console.print(
                        f"  {key}: <string> ({len(value)} chars)", style="magenta"
                    )
                else:
                    console.print(f"  {key}: {value}", style="magenta")

            # 1. Successful Summary
            summary_text = final_state.get("summary")
            final_error = final_state.get("error")

            if summary_text and not final_error:
                console.print("---AGENT FINISHED: Summary---", style="bold green")
                return summary_text

            # 2. Error occurred (could be init, extraction, or summarization error)
            elif final_error:
                console.print(
                    f"---AGENT FINISHED: Error ('{final_error}')---", style="bold red"
                )
                # Ensure the error message is prefixed consistently
                if final_error.lower().startswith("error:"):
                    return final_error
                else:
                    return "Error: " + final_error

            # 3. No Summary and No Error (Should ideally not happen with should_summarize logic)
            else:
                console.print(
                    "---AGENT FINISHED: Incomplete State---", style="bold yellow"
                )
                # Fallback error message
                return "Error: Agent finished without a summary or a specific error message."

        else:
            console.print("---AGENT FAILED: No Final State---", style="bold red")
            return "Error: Agent workflow did not produce a final state."

    except Exception as e:
        console.print("---AGENT FAILED: Runtime Exception---", style="bold red")
        console.print_exception(show_locals=False)
        return "Error: An unexpected error occurred in the agent: " + str(e)


# Example usage (for testing)
if __name__ == "__main__":
    import asyncio

    # --- Test Cases ---
    # Twitter/X URL (using the new tool)
    # test_url_msg = "Check out this thread: https://x.com/kargarisaac/status/1808919271263514745"
    test_url_msg = (
        "Summarize this tweet: https://x.com/natolambert/status/1917928418068541520"
    )

    # Standard Web URL (using Tavily)
    # test_url_msg = "Can you summarize this? https://lilianweng.github.io/posts/2023-06-23-agent/"

    # PDF URL
    # test_url_msg = "Summarize: https://arxiv.org/pdf/2305.15334.pdf"

    # URL that might fail primary extraction (Tavily might fail)
    # test_url_msg = "What about this? https://some-obscure-or-dynamic-page.com" # Example, replace if needed

    # Message without a URL
    # test_url_msg = "Hello, how are you?"

    async def main():
        print(f"Running agent for: {test_url_msg}")
        result = await run_agent(test_url_msg)
        print("\n--- FINAL RESULT ---")
        if result:
            # Ensure result is treated as a string before printing
            print(str(result))
        else:
            # Handle the case where run_agent might return None (though it aims not to)
            print("Agent returned None or an empty result.")

    asyncio.run(main())
