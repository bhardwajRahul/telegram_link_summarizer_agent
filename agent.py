# agent.py

import logging
# import os # Removed unused import
import re
import io
# Re-added Any for node return types
from typing import Annotated, Sequence, Optional, TypedDict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup
# HumanMessage is used in start_node
from langchain_core.messages import BaseMessage, HumanMessage
# Re-added StateGraph, END
from langgraph.graph import StateGraph, END
# Re-added SqliteSaver for checkpointing
from langgraph.checkpoint.sqlite import SqliteSaver
import requests
from firecrawl import FirecrawlApp
import baml_client
# Import necessary BAML types
from baml_client.types import ContentType, Content, GetContentResult, SummarizationResult
from pypdf import PdfReader
from baml_client import b


from config import (
    FIRECRAWL_API_KEY,
    # TAVILY_API_KEY, # Removed unused import
)

logger = logging.getLogger(__name__)

# --- BAML Client Initialization ---
try:
    baml = baml_client.BamlClient()
    logger.info("BAML Client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize BAML Client: {e}", exc_info=True)
    baml = None

# --- Tool Definitions ---
tavily_tool = None
# Conditional initialization if needed later
# if TAVILY_API_KEY:
#     try:
#         from langchain_community.tools.tavily_search import TavilySearchResults
#         tavily_tool = TavilySearchResults(max_results=3, api_key=TAVILY_API_KEY)
#         logger.info("Tavily search tool initialized.")
#     except Exception as e:
#         logger.error(f"Failed to initialize Tavily tool: {e}", exc_info=True)
# else:
#     logger.warning("TAVILY_API_KEY not found. Tavily tool disabled.")

firecrawl_client = None
if FIRECRAWL_API_KEY:
    try:
        firecrawl_client = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
        logger.info("Firecrawl client initialized.")
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
        response = requests.head(url, timeout=10, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/pdf" in content_type:
            return True
    except requests.RequestException as e:
        logger.warning(f"Could not check HEAD for {url}: {e}")
    return False


def extract_text_from_pdf(url: str) -> str:
    """Downloads a PDF from a URL and extracts text using pypdf."""
    logger.info(f"Attempting to extract text from PDF: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
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

        logger.info(f"Successfully extracted text from PDF: {url} (Length: {len(text)})")
        return text.strip()

    except requests.RequestException as e:
        logger.error(f"Failed to download PDF from {url}: {e}", exc_info=True)
        return f"Error: Could not download PDF from URL. {e}"
    except Exception as e:
        logger.error(f"Failed to process PDF content from {url}: {e}", exc_info=True)
        return f"Error: Could not process PDF content. {e}"


def basic_scrape_text(url: str) -> str:
    """Performs a basic scrape using requests and BeautifulSoup."""
    logger.info(f"Attempting basic scrape for URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        text = re.sub(r"\n\s*\n", "\n\n", text).strip()

        if not text:
            logger.warning(f"Basic scrape yielded no text for: {url}")
            return "Error: No text content found after basic scraping."

        logger.info(f"Basic scrape successful for {url} (Length: {len(text)})")
        return text

    except requests.RequestException as e:
        logger.error(f"Basic scrape failed for {url}: {e}", exc_info=True)
        return f"Error: Failed to fetch URL for basic scraping. {e}"
    except Exception as e:
        logger.error(f"Error during basic scraping processing for {url}: {e}", exc_info=True)
        return f"Error: Could not process HTML content. {e}"


def firecrawl_scrape(url: str) -> str:
    """Uses Firecrawl to scrape a URL."""
    if not firecrawl_client:
        logger.error("Firecrawl client not initialized. Cannot scrape.")
        return "Error: Firecrawl client not available. Check API Key."
    logger.info(f"Attempting Firecrawl scrape for URL: {url}")
    try:
        scraped_data = firecrawl_client.scrape_url(url, {'pageOptions': {'onlyMainContent': True}})
        if scraped_data and 'markdown' in scraped_data and scraped_data['markdown']:
            logger.info(f"Firecrawl scrape successful for {url} (Length: {len(scraped_data['markdown'])})")
            return scraped_data['markdown']
        elif scraped_data and 'content' in scraped_data and scraped_data['content']:
            logger.warning(f"Firecrawl returned content but no markdown for {url}. Using raw content.")
            soup = BeautifulSoup(scraped_data['content'], "html.parser")
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n\s*\n", "\n\n", text).strip()
            if text:
                logger.info(f"Firecrawl raw content extraction for {url} (Length: {len(text)})")
                return text
            else:
                 logger.error(f"Firecrawl scrape failed for {url}: No markdown or usable content found in response.")
                 return "Error: Firecrawl failed to extract meaningful content."
        else:
            logger.error(f"Firecrawl scrape failed for {url}: Empty or unexpected response format.")
            return "Error: Firecrawl returned no usable content."

    except Exception as e:
        logger.error(f"Firecrawl scrape failed for {url}: {e}", exc_info=True)
        return f"Error: Firecrawl encountered an error during scraping. {e}"


# --- BAML Functions Integration ---

async def get_content_from_url(url: str) -> GetContentResult:
    """
    Determines the type of content at the URL (PDF, web page) and extracts text.
    Uses Firecrawl as a fallback for complex web pages.
    Returns a BAML GetContentResult object.
    """
    logger.info(f"Getting content for URL: {url}")
    content_type = ContentType.WEBPAGE # Default assumption
    extracted_text = ""
    error_message = None
    MIN_BASIC_SCRAPE_LENGTH = 200 # Threshold for trying Firecrawl

    try:
        if is_pdf_url(url):
            content_type = ContentType.PDF
            extracted_text = extract_text_from_pdf(url)
        else:
            # Try basic scraping first
            content_type = ContentType.WEBPAGE
            extracted_text = basic_scrape_text(url)

            # If basic scrape fails or yields little text, try Firecrawl (if available)
            if extracted_text.startswith("Error:") or len(extracted_text) < MIN_BASIC_SCRAPE_LENGTH:
                 if firecrawl_client:
                     logger.warning(f"Basic scrape insufficient for {url} (length {len(extracted_text)}). Trying Firecrawl.")
                     firecrawl_text = firecrawl_scrape(url)
                     if not firecrawl_text.startswith("Error:"):
                         extracted_text = firecrawl_text
                         content_type = ContentType.WEBPAGE_FIRECRAWL # Indicate Firecrawl was used
                     else:
                         logger.warning(f"Firecrawl also failed for {url}. Using basic scrape result or error.")
                         if extracted_text.startswith("Error:"):
                             error_message = extracted_text # Keep basic scrape error
                         else: # Basic had *some* text but too little
                             error_message = f"Basic scrape yielded minimal content ({len(extracted_text)} chars). Firecrawl failed: {firecrawl_text}"
                         # Decide whether to clear text or keep minimal text
                         # Let's keep minimal text for now
                         if error_message and not extracted_text.startswith("Error:"):
                             error_message += " Using minimal basic text anyway." # Fixed multi-statement line and f-string

                 else:
                     logger.warning(f"Basic scrape insufficient for {url}, but Firecrawl is unavailable.")
                     if extracted_text.startswith("Error:"):
                         error_message = extracted_text # Keep basic scrape error
                     else: # Basic scrape had some text, but not enough
                         error_message = f"Basic scrape yielded minimal content ({len(extracted_text)} chars), and Firecrawl is unavailable."
                         # Keep the minimal text

        # Final check for errors from extraction functions
        if extracted_text.startswith("Error:"):
            error_message = extracted_text
            extracted_text = "" # Ensure text is empty on error

    except Exception as e:
        logger.error(f"Unexpected error during content extraction for {url}: {e}", exc_info=True)
        error_message = f"Unexpected error during content extraction: {e}"
        extracted_text = ""

    if error_message:
         logger.error(f"Failed to extract content from {url}: {error_message}")

    # Prepare BAML result using BAML-defined classes
    content_obj = Content(
        contentType=content_type,
        source=url,
        text=extracted_text, # Return potentially minimal text even if warning occurred
        metadata={"error": error_message} if error_message else {} # Store error separately
    )

    # Wrap in GetContentResult (assuming this is the BAML structure)
    result = GetContentResult(content=content_obj)
    logger.debug(f"GetContentResult for {url}: Type={result.content.contentType}, HasError={bool(result.content.metadata.get('error'))}, TextLength={len(result.content.text)}")
    return result


async def summarize_content(content: Content, query: Optional[str] = None) -> SummarizationResult:
    """Uses BAML to summarize the extracted content."""
    if not baml:
        logger.error("BAML client not initialized. Cannot summarize.")
        # Return a BAML-compatible error structure
        return SummarizationResult(summary="Error: Summarization service unavailable.", confidence=0.0, metadata={"error": "BAML client not initialized"})

    logger.info(f"Summarizing content from: {content.source} (Type: {content.contentType}, Length: {len(content.text)})")

    if not content.text:
        error_msg = content.metadata.get("error", "Content extraction yielded no text.")
        logger.warning(f"Cannot summarize empty content from {content.source}. Error: {error_msg}")
        return SummarizationResult(summary=f"Error: Cannot summarize. {error_msg}", confidence=0.0, metadata={"error": error_msg})

    # Check for previous non-critical error (like minimal content warning)
    previous_error = content.metadata.get("error")
    if previous_error:
        logger.warning(f"Proceeding with summarization for {content.source} despite previous warning: {previous_error}")

    try:
        # *** IMPORTANT: Verify BAML function name and signature ***
        # Assuming a BAML function 'SummarizeContent' exists and takes 'content' and 'query'
        summary_result: SummarizationResult = await b.SummarizeContent(content=content, query=query)

        logger.info(f"Summarization successful for {content.source}. Summary length: {len(summary_result.summary)}")
        # If summarization succeeds, potentially clear or note the previous non-critical error?
        # For now, just return the summary result.
        if previous_error and summary_result.metadata:
             summary_result.metadata['warning'] = previous_error # Preserve warning
        elif previous_error:
             summary_result.metadata = {'warning': previous_error}

        return summary_result

    except Exception as e:
        logger.error(f"BAML summarization failed for {content.source}: {e}", exc_info=True)
        error_msg = f"Summarization failed due to an internal error: {e}"
        # Return a BAML-compatible error structure
        return SummarizationResult(summary=f"Error: {error_msg}", confidence=0.0, metadata={"error": str(e)})


# --- LangGraph Agent State ---

class AgentState(TypedDict):
    # Use Annotated for the 'messages' accumulator
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    url: str # The URL to process
    content: Optional[Content] # Extracted content (using BAML Content type)
    summary: Optional[str] # Final summary text
    error: Optional[str] # Error message if processing fails


# --- LangGraph Nodes ---

async def start_node(state: AgentState) -> dict[str, Any]:
    """Initiates the process, extracting the URL from the initial message."""
    logger.info("Agent started - Start Node")
    # Assumes the last message is the user's request containing the URL
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        # Simple URL extraction (can be made more robust)
        # TODO: Improve URL extraction regex
        urls = re.findall(r'(https?://\S+)', last_message.content)
        if urls:
            url = urls[0]
            logger.info(f"Extracted URL: {url}")
            return {"url": url, "error": None}
        else:
            logger.error("No URL found in the initial message.")
            return {"error": "No URL found in the message."}
    else:
        logger.error("Last message is not a HumanMessage.")
        return {"error": "Invalid initial message type."}

async def fetch_content_node(state: AgentState) -> dict[str, Any]:
    """Fetches content from the URL using the get_content_from_url function."""
    logger.info("Fetching Content Node")
    url = state.get("url")
    if not url:
        logger.error("URL missing in state for fetching content.")
        return {"error": "URL missing in state.", "content": None}

    try:
        content_result = await get_content_from_url(url)
        logger.info(f"Content fetched for {url}. Type: {content_result.content.contentType}")
        # Store the BAML Content object directly
        return {"content": content_result.content, "error": content_result.content.metadata.get("error")}
    except Exception as e:
        logger.error(f"Error fetching content for {url}: {e}", exc_info=True)
        return {"error": f"Failed to fetch content: {e}", "content": None}

async def summarize_node(state: AgentState) -> dict[str, Any]:
    """Summarizes the fetched content using the BAML summarize_content function."""
    logger.info("Summarize Node")
    content = state.get("content")
    query = None # Add logic here if query needs to be extracted/passed

    if not content:
        logger.error("Content missing in state for summarization.")
        return {"error": "Content missing in state.", "summary": None}

    # If content extraction previously failed, propagate the error
    extraction_error = content.metadata.get("error")
    if not content.text and extraction_error:
        logger.warning(f"Skipping summarization due to previous extraction error: {extraction_error}")
        return {"error": f"Skipping summarization. {extraction_error}", "summary": None}

    try:
        summary_result = await summarize_content(content, query)
        logger.info(f"Content summarized for {content.source}")
        # Check if BAML returned an error during summarization
        baml_error = summary_result.metadata.get("error")
        if baml_error:
            logger.error(f"BAML summarization failed: {baml_error}")
            return {"error": f"Summarization failed: {baml_error}", "summary": None}
        else:
            return {"summary": summary_result.summary, "error": None} # Clear previous non-critical errors if summary is successful
    except Exception as e:
        logger.error(f"Error during summarization node execution for {content.source}: {e}", exc_info=True)
        return {"error": f"Summarization node failed: {e}", "summary": None}

async def error_node(state: AgentState) -> dict[str, Any]:
    """Handles errors accumulated during the process."""
    logger.error(f"Error Node reached. Error: {state.get('error')}")
    # Error is already in the state, this node just logs and allows the graph to end gracefully.
    return {}

# --- Conditional Edges ---

def should_continue(state: AgentState) -> str:
    """Determines the next step based on the current state (especially errors)."""
    logger.debug(f"Checking should_continue. Current error state: {state.get('error')}")
    if state.get("error"):
        logger.warning("Error detected, routing to error handler.")
        return "handle_error"
    # If content is not yet fetched, fetch it
    if not state.get("content"):
         return "fetch_content"
    # If content is fetched but not summarized, summarize it
    if not state.get("summary"):
        return "summarize"
    # If summary is present, finish
    return END


# --- Build Agent Graph ---

def create_agent_graph():
    """Builds the LangGraph agent."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("start", start_node)
    workflow.add_node("fetch_content", fetch_content_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("handle_error", error_node) # Node to transition to on error

    # Set entry point
    workflow.set_entry_point("start")

    # Add conditional edges
    workflow.add_conditional_edges(
        "start", # Start node transitions based on should_continue
        should_continue,
        {
            "fetch_content": "fetch_content",
            "handle_error": "handle_error",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "fetch_content", # Fetch node transitions based on should_continue
        should_continue,
        {
            "summarize": "summarize",
            "handle_error": "handle_error",
            END: END, # Should not happen directly from fetch if summarize is next
        },
    )
    workflow.add_conditional_edges(
        "summarize", # Summarize node transitions based on should_continue
        should_continue,
        {            
            "handle_error": "handle_error", # If summarize fails
            END: END, # If summarize succeeds
        },
    )

    # Error handling node always ends the graph
    workflow.add_edge("handle_error", END)

    # Compile the graph
    # Add checkpointer
    memory = SqliteSaver.from_conn_string(":memory:") # Use in-memory db for simplicity, replace if persistence needed
    agent_graph = workflow.compile(checkpointer=memory)
    logger.info("Agent graph compiled successfully.")
    return agent_graph

# --- Run Agent --- #

async def run_agent(input_message: str):
    """Runs the agent graph with the given input message."""
    agent_graph = create_agent_graph()
    config = {"configurable": {"thread_id": "user-session-1"}} # Example thread ID

    # Create initial state
    initial_state = {"messages": [HumanMessage(content=input_message)]}

    logger.info(f"Running agent with input: '{input_message[:50]}...'" )
    final_state = None
    try:
        async for event in agent_graph.astream(initial_state, config=config):
            # Process events if needed (e.g., print node outputs)
            # print(event)
            # Capture the final state
            if "messages" in event.get("__end__", {}):
                 final_state = event["__end__"]

        if final_state:
            logger.info("Agent finished successfully.")
            summary = final_state.get('summary')
            error = final_state.get('error')
            if error:
                logger.error(f"Agent finished with error: {error}")
                return f"Error processing link: {error}"
            elif summary:
                logger.info(f"Final Summary: {summary[:100]}...")
                return summary
            else:
                logger.warning("Agent finished but produced no summary or error.")
                return "Processing finished, but no summary was generated."
        else:
            logger.error("Agent finished without reaching a final state.")
            return "Error: Agent execution did not complete properly."

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return f"Error running agent: {e}"

# Example usage (for testing)
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    # Test URL
    # test_url = "https://example.com" # Replace with a real URL for testing
    test_url = "https://arxiv.org/pdf/2306.08302" # Example PDF
    result = asyncio.run(run_agent(f"Please summarize this link: {test_url}"))
    print("\n--- Agent Result ---")
    print(result)
    print("--------------------")
