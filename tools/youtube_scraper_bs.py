import re
import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def fetch_youtube_description_bs(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches the YouTube video description using requests and BeautifulSoup.

    Args:
        url: The YouTube video URL.

    Returns:
        A tuple containing:
            - str: The video description if found.
            - str: An error message if an error occurred, otherwise None.
    """
    log.info(f"Attempting YouTube description fetch via BeautifulSoup for: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.content, features="html.parser")

        # Attempt to find the description using the pattern you provided
        # This pattern looks for 'shortDescription":"' in the page source.
        # It's quite specific and might break if YouTube changes its page structure.
        pattern = re.compile('(?<=shortDescription":").*(?=","isCrawlable)')

        # Search for the pattern in the string representation of the soup
        # It's generally better to parse structured data if available (e.g., from <script> tags)
        # than to use regex on the whole HTML, but we'll stick to your method for now.
        script_tags = soup.find_all("script")
        description_match = None
        for script in script_tags:
            if script.string:  # Check if the script tag has content
                matches = pattern.findall(script.string)
                if matches:
                    description_match = matches[0]  # Take the first match
                    break

        if description_match:
            # The regex extracts the content between 'shortDescription":"' and '","isCrawlable"'
            # The .replace('\\n', '\\n') is to convert escaped newlines to actual newlines.
            description = description_match.replace("\\n", "\n").replace("\n", "\n")
            # Further unescape unicode sequences that might appear like \\u0026 for &
            description = description.encode("utf-8").decode("unicode_escape")
            log.info(f"Successfully fetched description via BeautifulSoup for: {url}")
            return description, None
        else:
            log.warning(f"BeautifulSoup couldn't find description pattern for: {url}")
            return None, "BeautifulSoup parser could not find the description pattern."

    except requests.exceptions.RequestException as e:
        log.error(f"BeautifulSoup request failed for {url}: {e}")
        return None, f"RequestException: {e}"
    except Exception as e:
        log.error(f"BeautifulSoup failed unexpectedly for {url}: {e}", exc_info=True)
        return None, f"Unexpected error in BeautifulSoup method: {e}"


if __name__ == "__main__":
    # Test cases
    test_urls = [
        "https://www.youtube.com/watch?v=q6pAWOG_10k",  # Your example
        "https://www.youtube.com/watch?v=DPXG4pdPj44",  # General video
        "https://www.youtube.com/watch?v=non_existent_video_id_xyz",  # Likely 404
    ]
    for test_url in test_urls:
        print(f"--- Testing URL: {test_url} ---")
        desc, err = fetch_youtube_description_bs(test_url)
        if err:
            print(f"Error: {err}")
        elif desc:
            print("Description Found:")
            print(desc[:500] + "..." if desc and len(desc) > 500 else desc)
        else:
            print("No description found and no error reported.")
        print("-" * 30)
