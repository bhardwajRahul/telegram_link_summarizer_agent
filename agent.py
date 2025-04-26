from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from baml_client import b
from baml_client.types import Summary, ContentType
import re

from rich.console import Console 
# Import tool functions
# from tools.scrape import is_pdf_url, extract_text_from_pdf
from tools.search import run_tavily_tool

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

def route_content_type(state: AgentState) -> AgentState:
    """Determines if the URL is a PDF or a webpage."""
    console.print("---ROUTING--- ", style="yellow bold")
    url = state['url']
    if url.lower().endswith('.pdf'):
        console.print(f"Routing to PDF handler for: {url}", style="blue")
        return "pdf_handler"
    else:
        console.print(f"Routing to Web Extract for: {url}", style="cyan")
        return "web_extractor"

def get_web_content(state: AgentState) -> AgentState:
    """Fetches content from a webpage URL."""
    console.print("---GET WEB CONTENT---", style="yellow bold")
    url = state['url']
    error_message=None
    try:
        extract_tool_results = run_tavily_tool(mode='extract', urls=[url])
        results_list = extract_tool_results.get('results', '')
        extract_content_source = ""
        for res in results_list:
            extract_content_source += f"URL: {res['url']}\n"
            extract_content_source += f"Raw Content: {res['raw_content']}\n"
            # extract_content_source += f"Images: {res['images']}\n"

        if len(extract_tool_results.get("failed_results", [])) > 0:
            error_message = extract_tool_results.get("failed_results")
            extract_content_source = ""
    except Exception as e:
        console.print(f"Error extracting content from URL {url}: {e}", style="red bold")
        error_message = f"Error: An unexpected error occurred while extracting content from the URL. {e}"
        extract_content_source = ""
    return {
        "content_type": ContentType.Webpage,
        "content": extract_content_source,
        "error": error_message
    }

def handle_pdf_content(state: AgentState) -> AgentState:
    """Placeholder for PDF content handling."""
    console.print("---HANDLE PDF CONTENT (Placeholder) ---", style="bold yellow")
    url = state['url']
    console.print(f"PDF handling not yet implemented for: {url}", style="magenta")
    # In the future, implement PDF extraction and RAG here
    # For now, returning an error or dummy content
    # return {"error": "PDF processing is not yet implemented."}
    return {"content": f"Placeholder content for PDF: {url}", "content_type": ContentType.PDF} # Allow summarization for now

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
            "pdf_handler": "pdf_handler",
        }
    )

    # Connect nodes
    workflow.add_edge("web_extractor", "summarizer")
    workflow.add_edge("pdf_handler", "summarizer")
    workflow.add_edge("summarizer", END)

    # Compile the graph
    app = workflow.compile()
    return app

graph = build_graph()

# --- Main Agent Function --- 
def run_agent(url: str) -> str:
    """Runs the LangGraph agent workflow."""
    console.print(f"--- Starting Agent for message: '{url[:50]}...' ---", style="bold blue")
    original_message  = f"Please summarize this link: {url}"
    initial_state = {"original_message": original_message, "url": url}
    try:
        # Or just invoke and get the final state
        app = build_graph()
        final_state = app.invoke(initial_state)

        console.print("--- Agent Finished ---", style="bold blue")
        if final_state.get('error'):
            console.print(f"Agent finished with error: {final_state['error']}", style="bold red")
            return f"Error: {final_state['error']}"
        elif final_state.get('summary'):
            console.print(f"Agent finished with summary: {final_state['summary'][:100]}...", style="green")
            return final_state['summary']
        else:
            console.print("Agent finished but no summary or error was produced.", style="yellow")
            return "Processing complete, but no summary was generated."

    except Exception as e:
        console.print(f"Unhandled exception in agent execution: {e}", style="bold red")
        return f"An unexpected error occurred: {e}"

# Example usage (for testing)
if __name__ == "__main__":
    url = "https://www.darioamodei.com/post/the-urgency-of-interpretability"
    result = run_agent(url=url)
    console.print(result, style="bold")
