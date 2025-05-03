import os
import re
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

API_BASE_URL = "https://api.twitterapi.io"
# Try reading with underscore first (common in container envs), fallback to hyphen
API_KEY = os.getenv("X_API_KEY") or os.getenv("X-API-KEY")


def _parse_twitter_datetime(datetime_str: str) -> datetime:
    """Parses Twitter's datetime string into a timezone-aware datetime object."""
    # Format: 'Thu May 01 12:03:30 +0000 2025'
    # Need to handle the +0000 timezone correctly
    try:
        # Standard format doesn't handle '+0000' directly as %z prior to Python 3.7/3.11 depending on platform?
        # Let's parse manually or use a robust library if needed.
        # For simplicity, assuming UTC (+0000)
        dt_naive = datetime.strptime(datetime_str, "%a %b %d %H:%M:%S +0000 %Y")
        return dt_naive.replace(tzinfo=timezone.utc)
    except ValueError:
        console.print(f"Error parsing datetime string: {datetime_str}", style="red")
        # Return epoch as a fallback to allow sorting even if parsing fails
        return datetime.fromtimestamp(0, tz=timezone.utc)


def fetch_tweet_thread(url: str) -> str:
    """
    Fetches the content of a tweet and its potential thread using twitterapi.io.

    Args:
        url: The URL of the tweet.

    Returns:
        A string containing the formatted tweet thread, or an error message starting with "Error:".
    """
    if not API_KEY:
        # Update error message to reflect both attempts
        return "Error: X_API_KEY or X-API-KEY not found in environment variables."

    # 1. Extract Tweet ID
    match = re.search(r"/status(?:es)?/(\d+)", url)
    if not match:
        return f"Error: Could not extract Tweet ID from URL: {url}"
    tweet_id = match.group(1)
    console.print(f"Extracted Tweet ID: {tweet_id}", style="cyan")

    headers = {"X-API-Key": API_KEY}
    all_tweets = []
    conversation_id = None
    main_tweet_data = None

    # 2. Fetch the main tweet
    try:
        console.print(f"Fetching main tweet ID: {tweet_id}", style="cyan")
        main_tweet_url = f"{API_BASE_URL}/twitter/tweets"
        params = {"tweet_ids": [tweet_id]}
        response = requests.get(main_tweet_url, headers=headers, params=params)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        data = response.json()

        if data.get("status") != "success" or not data.get("tweets"):
            error_msg = data.get("msg", "Unknown error")
            return f"Error: Failed to fetch main tweet {tweet_id}. API Status: {data.get('status')}, Msg: {error_msg}"

        main_tweet_data = data["tweets"][0]
        all_tweets.append(main_tweet_data)
        conversation_id = main_tweet_data.get("conversationId")
        console.print(
            f"Main tweet fetched. Conversation ID: {conversation_id}", style="green"
        )

    except requests.exceptions.RequestException as e:
        return f"Error: Network or API error fetching main tweet {tweet_id}: {e}"
    except Exception as e:
        return f"Error: Unexpected error processing main tweet response: {e}"

    # 3. Fetch the conversation/thread if conversationId is valid and different from tweet_id
    #    (A single tweet's conversationId is often its own tweet_id)
    if conversation_id and conversation_id != tweet_id:
        try:
            console.print(
                f"Fetching conversation thread ID: {conversation_id}", style="cyan"
            )
            thread_url = f"{API_BASE_URL}/twitter/tweet/advanced_search"
            params = {
                "query": f"conversation_id:{conversation_id}",
                # Optionally add 'sort_order': 'recency' if API supports it for chronological order
                # Add other filters if needed, like 'since_id' using the main tweet ID?
                # Check API docs for best way to get replies *after* the main tweet
            }
            response = requests.get(thread_url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "success" and data.get("tweets"):
                thread_tweets = data["tweets"]
                # Filter out the main tweet if it's included in the conversation results
                filtered_thread_tweets = [
                    t for t in thread_tweets if t.get("id") != tweet_id
                ]
                all_tweets.extend(filtered_thread_tweets)
                console.print(
                    f"Fetched {len(filtered_thread_tweets)} additional tweets in conversation.",
                    style="green",
                )
            elif data.get("status") != "success":
                console.print(
                    f"Warning: Failed to fetch conversation thread {conversation_id}. API Status: {data.get('status')}, Msg: {data.get('msg', 'Unknown error')}",
                    style="yellow",
                )
                # Proceed with only the main tweet

        except requests.exceptions.RequestException as e:
            console.print(
                f"Warning: Network or API error fetching conversation thread {conversation_id}: {e}",
                style="yellow",
            )
            # Proceed with only the main tweet
        except Exception as e:
            console.print(
                f"Warning: Unexpected error processing conversation thread response: {e}",
                style="yellow",
            )
            # Proceed with only the main tweet

    # 4. Sort tweets by creation date
    all_tweets.sort(
        key=lambda t: _parse_twitter_datetime(
            t.get("createdAt", "Thu Jan 01 00:00:00 +0000 1970")
        )
    )

    # 5. Format the output
    output_lines = []
    for i, tweet in enumerate(all_tweets):
        author_info = tweet.get("author", {})
        username = author_info.get("userName", "unknown_user")
        created_at_str = tweet.get("createdAt", "Unknown time")
        text = tweet.get("text", "").strip()

        # Basic formatting
        line = f"Tweet {i + 1}/{len(all_tweets)} by @{username} ({created_at_str}):\n{text}\n---"
        output_lines.append(line)

    if not output_lines:
        return f"Error: No tweet data could be formatted for tweet ID {tweet_id}."  # Should not happen if main tweet fetch succeeded

    return "\n".join(output_lines).strip()


# Example usage (for testing this script directly)
if __name__ == "__main__":
    # Test with a known tweet URL (replace with a real one, potentially a thread)
    # test_url_single = "https://x.com/levelsio/status/1798629243934064791" # Example single tweet
    test_url_thread_start = "https://x.com/omarsar0/status/1917939469103305013?s=52"  # Example thread start (replace if needed)

    print(f"--- Testing with URL: {test_url_thread_start} ---")
    result = fetch_tweet_thread(test_url_thread_start)
    print("\n--- RESULT ---")
    print(result)
    print("--- END TEST ---")
