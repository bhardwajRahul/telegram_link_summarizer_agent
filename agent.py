import os
import re
from typing import Any, Dict, TypedDict, Union

from baml_client import b
from baml_client.types import ContentType, Summary, ExtractorTool
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
    route_decision: str | None  # To store the routing decision string


# --- Define Graph Nodes ---


def init_state(state: AgentState) -> Dict[str, Any]:
    """Extracts the URL from the original message."""
    console.print("---INIT STATE---", style="yellow bold")
    message = state["original_message"]
    # Basic URL extraction (consider a more robust regex)
    url = next((word for word in message.split() if word.startswith("http")), None)
    error = None if url else "No URL found in the message."

    if error:
        console.print(f"Initialization error: {error}", style="red")

    return {
        "original_message": message,
        "url": url if url else "",  # Ensure url is always a string
        "content_type": ContentType.Webpage,
        "content": "",
        "summary": "",
        "error": error,
        "route_decision": None,
    }


async def llm_router(state: AgentState) -> Dict[str, Any]:
    """Determines the content extraction route using the BAML LLM Router."""
    console.print("---LLM ROUTER (BAML)--- ", style="yellow bold")

    # If init failed, pass the error along
    if state.get("error"):
        console.print(
            f"Skipping LLM Router due to init error: {state['error']}", style="red"
        )
        return {"error": state["error"], "route_decision": "__error__"}

    message = state["original_message"]
    decision = "__error__"  # Default to error
    routing_error = None

    try:
        console.print(
            f"Calling BAML RouteRequest for: '{message[:50]}...'", style="cyan"
        )
        # Call the BAML function (synchronously, as it's not declared async in BAML)
        route_result: ExtractorTool = b.RouteRequest(original_message=message)

        console.print(f"LLM Router returned: {route_result}", style="green")

        # Map the enum result to string for routing
        if route_result == ExtractorTool.WebpageExtractor:
            decision = "web_extractor"
        elif route_result == ExtractorTool.PDFExtractor:
            decision = "pdf_extractor"
        elif route_result == ExtractorTool.TwitterExtractor:
            decision = "twitter_extractor"
        elif route_result == ExtractorTool.Unsupported:
            decision = "__unsupported__"
            routing_error = "Unsupported URL type or no URL found by LLM Router."
            console.print(routing_error, style="yellow")
        else:
            # Should not happen if enum is handled correctly
            decision = "__error__"
            routing_error = f"LLM Router returned an unexpected value: {route_result}"
            console.print(routing_error, style="red")

    except Exception as e:
        console.print(f"Error calling BAML RouteRequest: {e}", style="red bold")
        routing_error = f"LLM Router failed: {e}"
        decision = "__error__"

    return {
        "route_decision": decision,
        "error": routing_error,  # Overwrite previous error state if routing fails
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
        if isinstance(content_result, str) and content_result.startswith("Error:"):
            error_message = content_result
            console.print(error_message, style="red bold")
            content_result = ""  # Ensure content is empty if tool errored
        elif not content_result:  # Handle empty success case
            error_message = "Twitter tool returned no content."
            console.print(error_message, style="yellow")
            content_result = ""
        else:
            console.print(
                f"Successfully fetched Twitter content for: {url}", style="green"
            )
            # Ensure content_result is a string
            if not isinstance(content_result, str):
                content_result = str(content_result)

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
        if isinstance(extracted_text, str) and extracted_text.startswith("Error:"):
            console.print(
                f"Error getting PDF content: {extracted_text}", style="red bold"
            )
            error_message = extracted_text
        elif not extracted_text:
            error_message = "PDF extraction returned no text."
            console.print(error_message, style="yellow")
        else:
            console.print(
                f"Successfully extracted text from PDF: {url}", style="magenta"
            )
            pdf_text = extracted_text
            # Ensure text is string
            if not isinstance(pdf_text, str):
                pdf_text = str(pdf_text)

    except Exception as e:
        console.print(f"Unexpected error handling PDF {url}: {e}", style="red bold")
        error_message = (
            f"Error: An unexpected error occurred while processing the PDF. {e}"
        )

    return {
        **state,
        "content": pdf_text.strip(),
        "content_type": ContentType.PDF,
        "error": error_message,
    }


async def summarize_content(state: AgentState) -> AgentState:
    """Summarizes the extracted content using BAML."""
    console.print("---SUMMARIZE CONTENT---", style="bold green")

    content_to_summarize = state.get("content")

    # If there was an error *before* summarization, don't proceed
    if state.get("error"):
        console.print(
            f"Skipping summarization due to previous error: {state['error']}",
            style="yellow",
        )
        return {**state, "summary": ""}  # Keep existing error

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
        # Ensure content_type is valid, default to Webpage if missing/invalid
        content_type = state.get("content_type", ContentType.Webpage)
        if not isinstance(content_type, ContentType):
            content_type = ContentType.Webpage  # Default fallback

        # Call the BAML function (synchronously, as it's not declared async in BAML)
        summary_result: Summary = b.SummarizeContent(
            content=content_to_summarize,
            content_type=content_type,
            context=state.get("original_message", ""),
        )
        console.print(f"Successfully generated summary.", style="bold green")
        title = getattr(summary_result, "title", "Summary")  # Default title
        key_points = getattr(summary_result, "key_points", [])
        concise_summary = getattr(
            summary_result,
            "concise_summary",
            "Summarization service returned an unexpected response format.",
        )

        # Ensure parts are strings
        title = str(title) if title else "Summary"
        key_points = [str(p).strip() for p in key_points if p]
        concise_summary = (
            str(concise_summary).strip() if concise_summary else "No summary generated."
        )

        formatted_summary = f"# {title}\n\n"
        if key_points:
            formatted_summary += "## Key Points:\n"
            for point in key_points:
                formatted_summary += f"- {point}\n"
            formatted_summary += "\n"  # Add space before summary
        formatted_summary += f"## Summary:\n{concise_summary}"
        formatted_summary = re.sub(r"\n\s*\n", "\n\n", formatted_summary).strip()

        # Clear any previous error if summarization succeeds
        summarization_error = None

    except Exception as e:
        console.print(f"Error during summarization for {url}: {e}", style="red bold")
        print(f"--- Debug: BAML summarization error: {e} ---")
        summarization_error = f"Summarization failed: {e}"
        formatted_summary = ""  # Ensure summary is empty on error

    # Keep the routing decision but update summary and error
    return {
        **state,
        "summary": formatted_summary,
        "error": summarization_error,  # Overwrite previous errors only if summarization fails
    }


# --- Conditional Edges Logic ---


def route_based_on_llm(state: AgentState) -> str:
    """Routes to the appropriate extractor based on the LLM router decision."""
    console.print("---ROUTING (LLM Decision)--- ", style="yellow bold")
    decision = state.get("route_decision")
    error = state.get("error")  # Check for errors from init or router node

    if error:
        console.print(f"Routing to END due to error: {error}", style="red")
        return END

    if decision == "web_extractor":
        console.print(f"LLM Routed to: Web Extractor", style="magenta")
        return "web_extractor"
    elif decision == "pdf_extractor":
        console.print(f"LLM Routed to: PDF Extractor", style="magenta")
        return "pdf_extractor"
    elif decision == "twitter_extractor":
        console.print(f"LLM Routed to: Twitter Extractor", style="magenta")
        return "twitter_extractor"
    elif decision == "__unsupported__":
        console.print("LLM Routed to: Unsupported -> END", style="yellow")
        # Error message should already be set by the router node
        return END
    else:  # Includes __error__ or unexpected values
        console.print(
            f"LLM Routing decision invalid or error ('{decision}'). Routing to END.",
            style="red",
        )
        # Ensure error state reflects this if not already set
        if not state.get("error"):
            state["error"] = f"Invalid routing decision: {decision}"
        return END


def should_summarize(state: AgentState) -> str:
    """Determines whether to proceed to summarization or end after extraction."""
    content = state.get("content")
    error = state.get("error")  # Check error from the *extractor* node
    has_content = content and isinstance(content, str) and content.strip() != ""

    if error:
        console.print(
            f"Routing after Extraction: Error occurred ('{error}'), routing to END.",
            style="red",
        )
        return END
    elif has_content:
        console.print(
            "Routing after Extraction: Content extracted successfully, routing to Summarize.",
            style="green",
        )
        return "summarize_content"
    else:
        console.print(
            "Routing after Extraction: No content extracted and no specific error, routing to END.",
            style="yellow",
        )
        # Set an error if none exists from the extractor
        state["error"] = (
            state.get("error") or "Content extraction finished with no content."
        )
        return END


# --- Build the Graph ---


def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("init", init_state)
    workflow.add_node("llm_router", llm_router)  # New router node
    workflow.add_node("web_extractor", get_web_content)
    workflow.add_node("pdf_extractor", handle_pdf_content)
    workflow.add_node("twitter_extractor", get_twitter_content)
    workflow.add_node("summarize_content", summarize_content)

    # Define edges
    workflow.set_entry_point("init")

    # Edge from init to the LLM router
    workflow.add_edge("init", "llm_router")

    # Conditional routing based on LLM Router output
    workflow.add_conditional_edges(
        "llm_router",
        route_based_on_llm,
        {
            "web_extractor": "web_extractor",
            "pdf_extractor": "pdf_extractor",
            "twitter_extractor": "twitter_extractor",
            END: END,  # Handles errors and unsupported cases from the router
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
    Runs the LangGraph agent workflow for URL summarization using an LLM router.

    Args:
        message: The original message potentially containing a URL.

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
            # output is a dictionary where keys are node names and values are states after the node ran
            # We are interested in the state *after* the last node executes
            node_name = list(output.keys())[0]
            final_state = output[node_name]  # Keep track of the latest state
            console.print(f"Output from node '{node_name}': Updated state", style="dim")
            # Optional: Print intermediate state details if needed for debugging
            # console.print(f"  State keys: {list(final_state.keys())}", style="dim")

        if final_state:
            # Debug: Print the final state (simplified)
            console.print("---FINAL STATE---", style="bold magenta")
            # Sort keys for consistent output order
            state_keys = sorted(final_state.keys())
            for key in state_keys:
                value = final_state[key]
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

            # Determine final result based on summary and error fields
            summary_text = final_state.get("summary")
            final_error = final_state.get("error")

            # 1. Successful Summary (even if there were intermediate, recoverable errors)
            if summary_text and isinstance(summary_text, str) and summary_text.strip():
                console.print("---AGENT FINISHED: Summary---", style="bold green")
                # If an error occurred *before* summarization, but summarization *still* happened
                # (e.g. fallback content used), we might want to mention the error.
                # For now, prioritize showing the summary if available.
                # if final_error:
                #     console.print(f"(Note: An earlier error occurred: {final_error})", style="yellow")
                return summary_text

            # 2. Error occurred (could be init, routing, extraction, or summarization error)
            elif final_error:
                console.print(
                    f"---AGENT FINISHED: Error ('{final_error}')---", style="bold red"
                )
                # Ensure the error message is prefixed consistently
                if isinstance(final_error, str) and final_error.lower().startswith(
                    "error:"
                ):
                    return final_error
                else:
                    return "Error: " + str(final_error)  # Ensure it's a string

            # 3. No Summary and No Error (Should ideally not happen with should_summarize logic,
            #    but could occur if summarizer returns empty without error)
            else:
                console.print(
                    "---AGENT FINISHED: No Summary/No Error---", style="bold yellow"
                )
                # Provide a more specific fallback message
                if not final_state.get("content"):
                    return "Error: Agent finished without extracting content."
                else:
                    return "Error: Agent finished. Content was extracted, but no summary was generated and no specific error was reported."

        else:
            console.print("---AGENT FAILED: No Final State---", style="bold red")
            return "Error: Agent workflow did not produce a final state."

    except Exception as e:
        console.print("---AGENT FAILED: Runtime Exception---", style="bold red")
        console.print_exception(show_locals=False)
        # Ensure the exception is converted to a string for the return value
        return "Error: An unexpected error occurred in the agent: " + str(e)


# Example usage (for testing)
if __name__ == "__main__":
    import asyncio

    # --- Test Cases ---
    # Twitter/X URL
    test_url_msg_twitter = (
        "Summarize this tweet: https://x.com/natolambert/status/1917928418068541520"
    )
    # Standard Web URL
    test_url_msg_web = (
        "Can you summarize this? https://lilianweng.github.io/posts/2023-06-23-agent/"
    )
    # PDF URL
    test_url_msg_pdf = "Summarize: https://arxiv.org/pdf/2305.15334.pdf"
    # URL that might fail primary extraction (Tavily might fail, but router should still pick web)
    test_url_msg_fail = (
        "What about this? https://httpbin.org/delay/5"  # Example, Tavily might timeout
    )
    # Message without a URL (Router should pick Unsupported)
    test_url_msg_nourl = "Hello, how are you?"
    # Unsupported URL Type (Router should pick Unsupported)
    test_url_msg_unsupported = "Check this out: ftp://files.example.com/data.zip"

    async def main():
        test_cases = {
            "Twitter": test_url_msg_twitter,
            "Web": test_url_msg_web,
            "PDF": test_url_msg_pdf,
            # "Web Fail": test_url_msg_fail, # May take time
            "No URL": test_url_msg_nourl,
            "Unsupported FTP": test_url_msg_unsupported,
        }

        for name, msg in test_cases.items():
            print(f"\n{'=/' * 10} RUNNING TEST: {name} {'=/' * 10}")
            print(f"Input message: {msg}")
            result = await run_agent(msg)
            print("\n--- FINAL RESULT ---")
            if result:
                # Ensure result is treated as a string before printing
                print(str(result))
            else:
                # Handle the case where run_agent might return None (though it aims not to)
                print("Agent returned None or an empty result.")
            print(f"{'=/' * 10} FINISHED TEST: {name} {'=/' * 10}\n")

    asyncio.run(main())
