import re
import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def fetch_youtube_title_bs(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches the YouTube video title using requests and BeautifulSoup, trying meta tags first.

    Args:
        url: The YouTube video URL.

    Returns:
        A tuple containing:
            - str: The video title if found.
            - str: An error message if an error occurred, otherwise None.
    """
    log.info(f"Attempting YouTube title fetch via BeautifulSoup for: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, features="html.parser")

        title: Optional[str] = None
        source_method: Optional[str] = None

        # Attempt 1: Meta og:title
        meta_og_title = soup.find("meta", property="og:title")
        if meta_og_title and meta_og_title.get("content"):
            title = meta_og_title.get("content").strip()
            if title:
                source_method = "META_OG"
                log.info(f"Found title via og:title meta tag for {url}: '{title}'")

        # Attempt 2: Meta itemprop:name
        if not title:
            meta_itemprop_name = soup.find("meta", itemprop="name")
            if meta_itemprop_name and meta_itemprop_name.get("content"):
                title = meta_itemprop_name.get("content").strip()
                if title:
                    source_method = "META_ITEMPROP"
                    log.info(
                        f"Found title via itemprop:name meta tag for {url}: '{title}'"
                    )

        # Attempt 3 (Fallback): HTML <title> tag
        if not title:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                raw_title = title_tag.string.strip()
                # Remove " - YouTube" suffix if present, as it's common in the <title> tag
                if raw_title.endswith(" - YouTube"):
                    title = raw_title[: -len(" - YouTube")].strip()
                else:
                    title = raw_title
                if title:
                    source_method = "HTML_TITLE_TAG"
                    log.info(f"Found title via HTML <title> tag for {url}: '{title}'")

        if title:
            log.info(
                f"Successfully fetched title (method: {source_method}) via BeautifulSoup for: {url}"
            )
            return title, None
        else:
            log.warning(
                f"BeautifulSoup couldn't find title using any method for: {url}"
            )
            return (
                None,
                "BeautifulSoup parser could not find the title using meta tags or title tag.",
            )

    except requests.exceptions.RequestException as e:
        log.error(f"BeautifulSoup request for title failed for {url}: {e}")
        return None, f"RequestException for title: {e}"
    except Exception as e:
        log.error(
            f"BeautifulSoup title fetch failed unexpectedly for {url}: {e}",
            exc_info=True,
        )
        return None, f"Unexpected error in BeautifulSoup title method: {e}"


def fetch_youtube_description_bs(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches the YouTube video description using requests and BeautifulSoup, trying multiple methods.

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

        description: Optional[str] = None
        source_method: Optional[str] = (
            None  # To track how description was found for logging/unescaping
        )

        # Attempt 1: Targeted HTML Element Search (e.g., for ytd-text-inline-expander)
        # This is often the most reliable for the full, user-visible description.
        expander = soup.find(
            "ytd-text-inline-expander", {"id": "description-inline-expander"}
        )
        if expander:
            content_holder = expander.find("yt-attributed-string", {"slot": "content"})
            if content_holder:
                raw_text = content_holder.get_text(separator="\\n", strip=True)
            else:  # Fallback to the whole expander's text
                raw_text = expander.get_text(separator="\\n", strip=True)

            if raw_text:
                # Clean common "Show more" / "Show less" / "Read more" text
                cleaned_text = re.sub(
                    r"\\nShow more\\n?", "", raw_text, flags=re.IGNORECASE
                ).strip()
                cleaned_text = re.sub(
                    r"\\nRead more\\n?", "", cleaned_text, flags=re.IGNORECASE
                ).strip()
                cleaned_text = re.sub(
                    r"\\nLess\\n?", "", cleaned_text, flags=re.IGNORECASE
                ).strip()  # For "Show less"
                if cleaned_text and len(cleaned_text) > 10:  # Basic sanity check
                    description = cleaned_text
                    source_method = "HTML_ELEMENT"
                    log.info(
                        f"Found description via HTML element (ytd-text-inline-expander) for: {url}"
                    )

        # Attempt 2: Meta og:description
        if not description:
            meta_og_desc = soup.find("meta", property="og:description")
            if meta_og_desc and meta_og_desc.get("content"):
                description = meta_og_desc.get("content").strip()
                if description:
                    source_method = "META_OG"
                    log.info(f"Found description via og:description meta tag for {url}")

        # Attempt 3: Meta itemprop:description
        if not description:
            meta_itemprop_desc = soup.find("meta", itemprop="description")
            if meta_itemprop_desc and meta_itemprop_desc.get("content"):
                description = meta_itemprop_desc.get("content").strip()
                if description:
                    source_method = "META_ITEMPROP"
                    log.info(
                        f"Found description via itemprop:description meta tag for {url}"
                    )

        # Attempt 4 (Fallback): Original regex method for 'shortDescription'
        if not description:
            log.info(
                f"No suitable description from HTML/meta, trying script regex for 'shortDescription': {url}"
            )
            pattern = re.compile('(?<=shortDescription":").*(?=","isCrawlable)')
            script_tags = soup.find_all("script")
            description_match = None
            for script in script_tags:
                if script.string:  # Check if the script tag has content
                    matches = pattern.findall(script.string)
                    if matches:
                        description_match = matches[0]  # Take the first match
                        break

            if description_match:
                desc_from_regex = description_match.replace(
                    "\\\\n", "\\n"
                )  # Correctly unescape \\n to \n
                # Further unescape unicode sequences that might appear like \\u0026 for &
                try:
                    # This handles unicode escapes like \uXXXX and other JSON string escapes
                    # We need to ensure the string is properly quoted for json.loads
                    # A common way is to treat it as a value within a JSON string
                    import json  # Make sure json is imported

                    description = json.loads(f'"{desc_from_regex}"')
                except (json.JSONDecodeError, TypeError):
                    # Fallback to a simpler unicode unescape if json.loads fails (e.g. complex nested quotes)
                    # This was closer to the original approach but unicode_escape can be tricky.
                    # Using 'latin-1' to preserve backslashes for unicode_escape
                    description = desc_from_regex.encode(
                        "latin-1", "backslashreplace"
                    ).decode("unicode-escape")

                source_method = "REGEX_SHORT_DESC"
                log.info(
                    f"Successfully fetched description via SCRIPT REGEX (shortDescription) for: {url}"
                )

        if description:
            log.info(
                f"Successfully fetched description (method: {source_method}) via BeautifulSoup for: {url}"
            )
            return description.strip(), None
        else:
            log.warning(
                f"BeautifulSoup methods couldn't find description pattern for: {url}"
            )
            return (
                None,
                "BeautifulSoup parser could not find the description using various methods.",
            )

    except requests.exceptions.RequestException as e:
        log.error(f"BeautifulSoup request failed for {url}: {e}")
        return None, f"RequestException: {e}"
    except Exception as e:
        log.error(f"BeautifulSoup failed unexpectedly for {url}: {e}", exc_info=True)
        return None, f"Unexpected error in BeautifulSoup method: {e}"


def fetch_youtube_details_bs(
    url: str,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Fetches the YouTube video title and description using BeautifulSoup.

    Args:
        url: The YouTube video URL.

    Returns:
        A tuple containing:
            - str: The video title if found.
            - str: The video description if found.
            - str: An error message for title fetching if an error occurred, otherwise None.
            - str: An error message for description fetching if an error occurred, otherwise None.
    """
    log.info(
        f"Attempting YouTube title and description fetch via BeautifulSoup for: {url}"
    )
    title, title_err = fetch_youtube_title_bs(url)
    description, desc_err = fetch_youtube_description_bs(url)

    if title or description:
        log.info(
            f"Successfully fetched some details via BeautifulSoup for: {url}. Title found: {title is not None}, Description found: {description is not None}"
        )
    else:
        log.warning(
            f"Failed to fetch any details (title/description) via BeautifulSoup for: {url}"
        )

    return title, description, title_err, desc_err


if __name__ == "__main__":
    # Test cases
    test_urls = [
        # "https://www.youtube.com/watch?v=q6pAWOG_10k&t=1213s",  # Jeff Dean talk (should have full desc)
        "https://www.youtube.com/watch?v=jNx5QRC1uqI",  # Rick Astley
    ]
    for test_url in test_urls:
        print(f"--- Testing URL: {test_url} with fetch_youtube_details_bs ---")
        title, desc, title_e, desc_e = fetch_youtube_details_bs(test_url)

        if title_e:
            print(f"Title Error: {title_e}")
        if desc_e:
            print(f"Description Error: {desc_e}")

        if title:
            print("Title Found:")
            print(title)
        else:
            print("No title found.")

        if desc:
            print("Description Found:")
            print(desc)
        else:
            print("No description found.")

        if not title and not desc and not title_e and not desc_e:
            print("No details found and no errors reported.")
        print("-" * 30)
