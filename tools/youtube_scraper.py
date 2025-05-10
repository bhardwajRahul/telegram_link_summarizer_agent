import logging
import os
import re
from typing import Dict, Optional, Tuple, Union

import requests  # To potentially fetch the transcript later if yt-dlp gives URL
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from yt_dlp import YoutubeDL

# Import the new BeautifulSoup scraper
from tools.youtube_scraper_bs import fetch_youtube_details_bs

# Load environment variables
load_dotenv()

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
log = logging.getLogger(__name__)
logging.getLogger("googleapiclient.discovery_cache").setLevel(
    logging.ERROR
)  # Silence noisy cache logs

# Constants
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Helper Functions ---


def _extract_video_id(url: str) -> Optional[str]:
    """Extracts YouTube video ID from various URL formats."""
    patterns = [
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&\"\'<> #]+)",
        r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?\"\'<> #]+)",
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?\"\'<> #]+)",
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([^?\"\'<> #]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    log.warning(f"Could not extract YouTube video ID from URL: {url}")
    return None


def _try_yt_dlp(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Attempts to fetch description and transcript URL using yt-dlp.

    Returns:
        Tuple (description, transcript_content, error_message)
        Transcript_content is None if only URL is found.
    """
    log.info(f"Attempting YouTube fetch via yt-dlp for: {url}")
    opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": False,  # Prefer auto-subs for consistency
        "sublangs": ["en"],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": log,  # Use our logger
        # Adding cookie handling options - these usually require user setup
        # 'cookiesfrombrowser': ('chrome', ), # Example: if you have Chrome cookies setup
        # 'cookiefile': 'path/to/cookies.txt', # Example: if using exported cookies
    }

    description = None
    transcript_url = None
    error_msg = None

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                url, download=False, process=True
            )  # process=True might help resolve some formats

        description = info.get("description")

        # Look for automatic captions first
        auto_caps = info.get("automatic_captions", {})
        en_auto_caps = auto_caps.get("en", [])
        if en_auto_caps:
            # Prioritize common text formats (vtt, ttml, srv3), fallback to any
            cap_info = next(
                (c for c in en_auto_caps if c.get("ext") in ["vtt", "ttml", "srv3"]),
                None,
            )
            if not cap_info and en_auto_caps:
                cap_info = en_auto_caps[0]  # Fallback

            if cap_info:
                transcript_url = cap_info.get("url")
                log.info(f"yt-dlp found transcript URL (format: {cap_info.get('ext')})")
                # Note: We *could* download and parse the transcript here,
                # but youtube-transcript-api is often more direct for the text.
                # We'll just return the description and None for transcript content for now.

        if not description and not transcript_url:
            log.warning(f"yt-dlp yielded no description or transcript URL for {url}")
            # Don't set error yet, let fallbacks try

    except Exception as e:
        # Check for specific common errors
        if "Sign in to confirm you're not a bot" in str(e):
            error_msg = (
                "yt-dlp Error: YouTube requires sign-in (cookies might be needed)."
            )
            log.warning(error_msg)
        elif "Video unavailable" in str(e):
            error_msg = "yt-dlp Error: Video seems unavailable."
            log.warning(error_msg)
        else:
            error_msg = f"yt-dlp Error: An unexpected error occurred: {e}"
            log.error(
                f"yt-dlp failed for {url}: {e}", exc_info=False
            )  # Keep log concise

    # yt-dlp primarily gives description. Transcript part is handled by youtube-transcript-api better.
    return description, None, error_msg


def _try_transcript_api(video_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Attempts to fetch transcript text using youtube-transcript-api.

    Returns:
        Tuple (transcript_text, error_message)
    """
    log.info(
        f"Attempting transcript fetch via youtube-transcript-api for ID: {video_id}"
    )
    transcript_text = None
    error_msg = None
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Find English transcript (manual or generated)
        transcript = transcript_list.find_transcript(["en"])
        fetched_transcript = transcript.fetch()

        if fetched_transcript:
            transcript_text = "\\n".join(
                [entry["text"] for entry in fetched_transcript]
            )
            log.info(
                f"Successfully fetched transcript via youtube-transcript-api for ID: {video_id}"
            )
        else:
            log.warning(
                f"youtube-transcript-api fetch succeeded but returned empty transcript for ID: {video_id}"
            )

    except (TranscriptsDisabled, NoTranscriptFound):
        error_msg = "Transcript API Error: Transcripts are disabled or no English transcript found."
        log.warning(f"{error_msg} (ID: {video_id})")
    except Exception as e:
        error_msg = f"Transcript API Error: An unexpected error occurred: {e}"
        log.error(f"youtube-transcript-api failed for {video_id}: {e}", exc_info=False)

    return transcript_text, error_msg


def _try_youtube_data_api(video_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Attempts to fetch description using YouTube Data API v3.

    Returns:
        Tuple (description, error_message)
    """
    if not GEMINI_API_KEY:
        return None, "YouTube Data API Error: GEMINI_API_KEY not configured."

    log.info(f"Attempting description fetch via YouTube Data API for ID: {video_id}")
    description = None
    error_msg = None

    try:
        youtube = build(
            "youtube", "v3", developerKey=GEMINI_API_KEY, cache_discovery=False
        )  # Disable cache
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()

        if response.get("items"):
            description = response["items"][0].get("snippet", {}).get("description")
            log.info(
                f"Successfully fetched description via YouTube Data API for ID: {video_id}"
            )
        else:
            log.warning(f"YouTube Data API returned no items for video ID: {video_id}")
            # Don't set error, maybe video exists but API behaves weirdly

    except HttpError as e:
        error_msg = (
            f"YouTube Data API Error: HTTP error {e.resp.status} occurred: {e.content}"
        )
        log.error(
            f"YouTube Data API failed for {video_id}: {error_msg}", exc_info=False
        )
    except Exception as e:
        error_msg = f"YouTube Data API Error: An unexpected error occurred: {e}"
        log.error(f"YouTube Data API failed for {video_id}: {e}", exc_info=False)

    return description, error_msg


# --- Main Function ---


def fetch_youtube_content_with_fallbacks(url: str) -> Union[str, Dict[str, str]]:
    """
    Fetches YouTube video title, description and transcript using multiple methods with fallbacks.

    Tries methods in order: BeautifulSoup (for title and description), yt-dlp (description),
    youtube-transcript-api (transcript), YouTube Data API v3 (description).
    Combines results into a markdown string.

    Args:
        url: The YouTube video URL.

    Returns:
        - A string containing the formatted content (title, description and/or transcript).
        - An error dictionary {"error": "message"} if all methods fail or a critical error occurs early.
    """
    log.info(f"Fetching YouTube content for URL: {url}")
    video_id = _extract_video_id(url)
    if not video_id:
        return {"error": f"Could not extract YouTube video ID from URL: {url}"}

    final_title: Optional[str] = None
    final_description: Optional[str] = None
    final_transcript: Optional[str] = None
    errors = []  # Collect errors from each step

    potential_descriptions: Dict[str, str] = {}
    bs_title_error: Optional[str] = None  # Specific error for BS title fetching
    bs_desc_error: Optional[str] = None  # Specific error for BS desc fetching

    # 0. Try BeautifulSoup scraper (for title and potentially a description)
    log.info(
        f"Attempting YouTube title and description fetch via BeautifulSoup for: {url}"
    )
    bs_title_val, bs_desc_val, bs_title_err_str, bs_desc_err_str = (
        fetch_youtube_details_bs(url)
    )

    if bs_title_val:
        final_title = bs_title_val  # Usually, title from BS is good enough if found
        log.info(f"Successfully fetched title via BeautifulSoup for: {url}")
    if bs_title_err_str:
        bs_title_error = f"BeautifulSoup (Title): {bs_title_err_str}"
        # Don't add to main errors yet, allow other methods to try for title if we were to add title fallbacks

    if bs_desc_val:
        potential_descriptions["bs"] = bs_desc_val
        log.info(
            f"BeautifulSoup provided a description candidate (length: {len(bs_desc_val)}) for: {url}"
        )
    if bs_desc_err_str:
        bs_desc_error = f"BeautifulSoup (Description): {bs_desc_err_str}"
        # Don't add to main errors yet, other methods will try for description

    # 1. Try yt-dlp (for description)
    log.info(f"Attempting description fetch via yt-dlp for: {url}")
    desc_dlp, _, err_dlp = _try_yt_dlp(url)
    if desc_dlp:
        potential_descriptions["dlp"] = desc_dlp
        log.info(
            f"yt-dlp provided a description candidate (length: {len(desc_dlp)}) for: {url}"
        )
    if err_dlp:
        errors.append(f"yt-dlp (Description): {err_dlp}")
        log.warning(f"yt-dlp failed for description for {url}: {err_dlp}")

    # 2. Try youtube-transcript-api (for transcript text - independent of description)
    transcript_api, err_transcript = _try_transcript_api(video_id)
    if transcript_api:
        final_transcript = transcript_api
    if err_transcript:
        errors.append(f"Transcript API: {err_transcript}")

    # 3. Try YouTube Data API v3 (for description - and potentially title if we extend _try_youtube_data_api)
    if GEMINI_API_KEY:  # Only try if API key is available
        log.info(
            f"Attempting description fetch via YouTube Data API for ID: {video_id}"
        )
        # Assuming _try_youtube_data_api primarily returns description for now.
        # If it were extended to return title: title_api, desc_api, err_api = _try_youtube_data_api(video_id)
        desc_api, err_api = _try_youtube_data_api(video_id)
        if desc_api:
            potential_descriptions["api"] = desc_api
            log.info(
                f"YouTube Data API provided a description candidate (length: {len(desc_api)}) for ID: {video_id}"
            )
        if err_api:
            errors.append(f"YouTube Data API (Description): {err_api}")
            log.warning(
                f"YouTube Data API failed for description for {video_id}: {err_api}"
            )

        # Fallback for title if BS didn't get it and API could provide it
        # if not final_title and title_api: # Example if _try_youtube_data_api returned title
        #     final_title = title_api
        #     log.info(f"YouTube Data API provided title for ID: {video_id}")

    # Determine the best description from collected candidates
    if potential_descriptions:
        # Find the key of the longest description string in the dictionary
        best_source_key = max(
            potential_descriptions, key=lambda k: len(potential_descriptions[k])
        )
        final_description = potential_descriptions[best_source_key]
        log.info(
            f"Selected description from source '{best_source_key}' (length: {len(final_description)}) for {url}. Available sources: {list(potential_descriptions.keys())}"
        )
    else:
        log.info(f"No description candidates found from any source for {url}")
        # If BS description specifically had an error and nothing else was found
        if bs_desc_error:
            errors.append(bs_desc_error)

    # If title is still missing and BS had a specific error for title
    if not final_title and bs_title_error:
        errors.append(bs_title_error)

    # --- Combine and Format ---
    output_parts = []
    if final_title:
        output_parts.append(f"**Video Title:**\n{final_title.strip()}")

    if final_description:
        output_parts.append(
            f"**Video Description:**\n```\n{final_description.strip()}\n```"
        )

    if final_transcript:
        output_parts.append(
            f"**Video Transcript:**\n```\n{final_transcript.strip()}\n```"
        )

    if output_parts:
        log.info(
            f"Successfully gathered content for {video_id}. Title: {final_title is not None}, Description: {final_description is not None}, Transcript: {final_transcript is not None}"
        )
        # Log collected errors if any content was successfully gathered
        if errors:
            log.warning(
                f"Partial success for {video_id}. Errors encountered: {'; '.join(errors)}"
            )
        return "\n\n".join(output_parts)
    else:
        # All methods failed to get *any* content
        error_summary = (
            "; ".join(errors)
            if errors
            else "All methods failed without specific errors."
        )
        log.error(
            f"Failed to retrieve any YouTube content for {video_id}. Errors: {error_summary}"
        )
        # Return a specific error key for the agent to handle fallback
        return {"error": "youtube_fallback_failed", "details": error_summary}


# Example usage (for testing)
if __name__ == "__main__":
    # Test cases
    # url_rick = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Often triggers bot detection
    url_regular = (
        "https://www.youtube.com/watch?v=q6pAWOG_10k&t=1213s"  # Should have subs
    )
    url_no_subs = (
        "https://www.youtube.com/watch?v=xxxxxxxxxxx"  # Non-existent video ID example
    )
    url_needs_login = "https://www.youtube.com/watch?v=hhMXE9-JUAc"  # Might need login/cookies for yt-dlp

    test_urls = {
        "Regular Video": url_regular,
        # "Needs Login/Cookie Video": url_needs_login,
        "Non-Existent Video": url_no_subs,
    }

    for name, test_url in test_urls.items():
        print(f"\n--- Testing: {name} ({test_url}) ---")
        result = fetch_youtube_content_with_fallbacks(test_url)
        if isinstance(result, dict) and "error" in result:
            print(f"Error: {result['error']}")
            if "details" in result:
                print(f"Details: {result['details']}")
        elif isinstance(result, str):
            print("Success! Content:")
            print(result)
        else:
            print(f"Unexpected return type: {type(result)}")
