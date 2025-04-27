from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from baml_client import b
from baml_client.types import Summary, ContentType
import re
from dotenv import load_dotenv
import os
import tweepy

from rich.console import Console 
from tools.search import run_tavily_tool
from tools.pdf_handler import get_pdf_text

load_dotenv()

console = Console()

# --- LangGraph Agent State ---

class AgentState(TypedDict):
    original_message: str
    url: str
    content_type: ContentType # 'web' or 'pdf'
    content: str
    summary: str
    error: str | None

# --- Define Graph Nodes --- 

def init_state(state: AgentState) -> Dict[str, Any]:
    """Extracts the URL from the original message."""
    console.print("---INIT STATE---", style="yellow bold")
    message = state['original_message']
    # Basic URL extraction (consider a more robust regex)
    url = next((word for word in message.split() if word.startswith('http')), None)
    if not url:
        return {"error": "No URL found in the message."}
    return {"url": url}

def route_content_type(state: AgentState) -> str:
    """Determines if the URL is a PDF, Twitter/X, or a webpage."""
    console.print("---ROUTING--- ", style="yellow bold")
    url = state['url']
    if url.lower().endswith('.pdf'):
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
    url = state['url']
    error_message = None
    content_source = ""
    content_type = ContentType.Webpage

    try:
        # Use Tavily extract for non-Twitter URLs
        console.print(f"Using Tavily extract for: {url}", style="cyan")
        extract_tool_results = run_tavily_tool(mode='extract', urls=[url])
        results_list = extract_tool_results.get('results', [])
        failed_results = extract_tool_results.get("failed_results", [])

        if results_list:
            for res in results_list:
                # Try to get 'raw_content' first, fallback to 'content'
                raw_content = res.get('raw_content')
                if not raw_content:
                    raw_content = res.get('content', '') # Fallback if raw_content is missing
                
                if raw_content: # Only add if content exists
                    content_source += f"URL: {res.get('url', 'N/A')}\n"
                    content_source += f"Raw Content: {raw_content}\n\n"
                # Optional: Include images if needed later
                # content_source += f"Images: {res.get('images', [])}\n"
        
        if failed_results:
            error_message = f"Tavily failed to extract content from: {', '.join(failed_results)}"
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
        content_source = "" # Ensure content is empty on error

    return {
        "content_type": content_type,
        "content": content_source.strip(), # Strip leading/trailing whitespace
        "error": error_message
    }

def get_twitter_content(state: AgentState) -> AgentState:
    """Fetches content from a Twitter/X URL using tweepy."""
    console.print("---GET TWITTER/X CONTENT (tweepy)---", style="yellow bold")
    url = state['url']
    error_message = None
    tweet_text = ""
    content_type = ContentType.Webpage # Treat as webpage for summarization

    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        error_message = "Error: X_BEARER_TOKEN not found in environment variables."
        console.print(error_message, style="red bold")
        return {
            "content_type": content_type,
            "content": "",
            "error": error_message
        }

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
        response = client.get_tweet(tweet_id, tweet_fields=["created_at", "public_metrics", "author_id"])

        if response.data:
            tweet = response.data
            # Fetch user details for the author ID
            user_response = client.get_user(id=tweet.author_id)
            username = user_response.data.username if user_response.data else "unknown_user"
            tweet_text = f"@{username} ({tweet.created_at}): {tweet.text}"
            console.print(f"Successfully fetched tweet: {tweet.id}")
        else:
            # Handle cases where the tweet might be deleted, private, or ID invalid
            error_detail = "Unknown reason."
            if response.errors:
                error_detail = "; ".join([e.get('detail', str(e)) for e in response.errors])
            error_message = f"Tweepy could not find or access tweet ID: {tweet_id}. Reason: {error_detail}"
            console.print(error_message, style="red")

    except tweepy.errors.TweepyException as e:
        console.print(f"Tweepy API error for URL {url}: {e}", style="red bold")
        error_message = f"Error: A Tweepy API error occurred: {e}"
    except ValueError as e: # Catch the ID extraction error
        console.print(f"Error processing Twitter URL {url}: {e}", style="red bold")
        error_message = f"Error: {e}"
    except Exception as e:
        console.print(f"Unexpected error getting content from Twitter/X URL {url} using tweepy: {e}", style="red bold")
        error_message = f"Error: An unexpected error occurred while getting Twitter/X content via tweepy. {e}"

    return {
        "content_type": content_type,
        "content": tweet_text.strip(),
        "error": error_message
    }

def handle_pdf_content(state: AgentState) -> AgentState:
    """Downloads and extracts text from a PDF URL."""
    console.print("---HANDLE PDF CONTENT---", style="bold yellow")
    url = state['url']
    error_message = None
    pdf_text = ""
    try:
        extracted_text = get_pdf_text(url)
        if extracted_text.startswith("Error:"):
            console.print(f"Error getting PDF content: {extracted_text}", style="red bold")
            error_message = extracted_text
        else:
            console.print(f"Successfully extracted text from PDF: {url}", style="magenta")
            pdf_text = extracted_text

    except Exception as e:
        console.print(f"Unexpected error handling PDF {url}: {e}", style="red bold")
        error_message = f"Error: An unexpected error occurred while processing the PDF. {e}"

    return {
        "content": pdf_text,
        "content_type": ContentType.PDF,
        "error": error_message
    }

def summarize_content(state: AgentState) -> AgentState:
    """Summarizes the extracted content using BAML."""
    console.print("---SUMMARIZE CONTENT---", style="bold green")
    # Check for errors from previous steps FIRST
    if state.get('error'):
        console.print(f"Skipping summarization due to previous error: {state['error']}", style="bold yellow")
        # Ensure summary is empty if skipped
        return {"summary": state.get('summary', '')}

    content = state.get('content') # Use .get() for safety, though error check should cover it
    if not content:
        console.print("Skipping summarization due to empty content.", style="yellow")
        # Ensure summary is empty if skipped
        return {"summary": state.get('summary', '')}

    try:
        # Assuming Summarize is the correct BAML function name based on baml_src/summarize.baml
        summary_result: Summary = b.SummarizeContent(
            content=state['content'],
            contentType=state['content_type'],
            context=state['original_message']
        )
        console.print("Successfully generated summary.", style="bold green")
        title = getattr(summary_result, 'title', 'Error')
        points = getattr(summary_result, 'key_points', [])
        summary = getattr(summary_result, 'concise_summary', 'Summarization service returned an unexpected response format.')

        formatted_summary = f"# {title}\n\n"
        formatted_summary += "## Key Points:\n"
        for point in points:
            # Basic cleanup: strip whitespace from each point
            formatted_summary += f"- {point.strip()}\n"
        formatted_summary += f"\n## Summary:\n{summary.strip()}"
        # Clean up potential multiple newlines or leading/trailing whitespace in the final string
        formatted_summary = re.sub(r'\n\s*\n', '\n\n', formatted_summary).strip()

        return {"summary": formatted_summary, "error": None}

    except Exception as e:
        console.print(f"Error during summarization: {e}", style="bold red")
        return {"error": f"Failed to summarize content: {e}"}

def build_graph():
    # --- Build the Graph --- 
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("init", init_state)
    workflow.add_node("web_extractor", get_web_content)
    workflow.add_node("twitter_extractor", get_twitter_content)
    workflow.add_node("pdf_handler", handle_pdf_content)
    workflow.add_node("summarizer", summarize_content)

    # Set entry point
    workflow.set_entry_point("init")

    # Add conditional routing
    workflow.add_conditional_edges(
        "init",
        route_content_type,
        {
            "web_extractor": "web_extractor",
            "twitter_extractor": "twitter_extractor",
            "pdf_handler": "pdf_handler",
        }
    )

    # Connect nodes
    workflow.add_edge("web_extractor", "summarizer")
    workflow.add_edge("twitter_extractor", "summarizer")
    workflow.add_edge("pdf_handler", "summarizer")
    workflow.add_edge("summarizer", END)

    # Compile the graph
    app = workflow.compile()
    return app


graph = build_graph()

# --- Main Agent Function --- 
def run_agent(url: str) -> str | None:
    """Runs the LangGraph agent workflow. Returns summary on success, None otherwise."""
    console.print(f"--- Starting Agent for message: '{url[:50]}...' ---", style="bold blue")
    original_message  = f"Please summarize this link: {url}"
    initial_state = {"original_message": original_message, "url": url}
    try:
        # Or just invoke and get the final state
        final_state = graph.invoke(initial_state)

        console.print("--- Agent Finished ---", style="bold blue")
        if final_state.get('error'):
            console.print(f"Agent finished with error: {final_state['error']}", style="bold red")
            return None
        elif final_state.get('summary'):
            console.print(f"Agent finished with summary: {final_state['summary'][:100]}...", style="green")
            return final_state['summary']
        else:
            console.print("Agent finished but no summary or error was produced.", style="yellow")
            return None

    except Exception as e:
        console.print(f"Unhandled exception in agent execution: {e}", style="bold red")
        return None

# Example usage (for testing)
if __name__ == "__main__":
    url = "https://www.darioamodei.com/post/the-urgency-of-interpretability"
    result = run_agent(url=url)
    console.print(result, style="bold")
