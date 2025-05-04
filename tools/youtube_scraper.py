import logging
from typing import Dict, Optional, Union
from yt_dlp import YoutubeDL
import requests  # To potentially fetch the transcript later

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def fetch_youtube_info(url: str) -> Union[Dict[str, Optional[str]], str]:
    """
    Fetches video description and English auto-caption URL from a YouTube URL using yt-dlp.

    Args:
        url: The YouTube video URL.

    Returns:
        A dictionary containing 'description' and 'transcript_url' if successful,
        otherwise an error message string.
    """
    logging.info(f"Attempting to fetch YouTube info for: {url}")

    # yt-dlp options:
    # skip_download: Don't download the video file.
    # writeautomaticsub: Try to get auto-generated captions.
    # writesubtitles: Try to get manually uploaded captions (set to False for now).
    # sublangs: Specify languages for subtitles/captions (request English).
    # noplaylist: If a playlist URL is given, only process the video specified.
    opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": False,
        "sublangs": ["en"],  # Request English captions/subtitles
        "noplaylist": True,  # Important if you only want the single video info
        "quiet": True,  # Suppress yt-dlp console output
        "no_warnings": True,  # Suppress warnings
        "logger": logging.getLogger("yt_dlp"),  # Optional: Direct yt-dlp logs
    }

    try:
        with YoutubeDL(opts) as ydl:
            # Extract information without downloading
            info = ydl.extract_info(url, download=False)

        description = info.get("description")
        transcript_url = None

        # Look for automatic captions (auto-generated)
        auto_caps = info.get("automatic_captions", {})
        en_auto_caps = auto_caps.get("en", [])
        if en_auto_caps:
            # Find the SRT format if available, otherwise take the first available format
            srt_cap = next(
                (
                    cap
                    for cap in en_auto_caps
                    if cap.get("ext") == "srv3"
                    or cap.get("ext") == "ttml"
                    or cap.get("ext") == "vtt"
                ),
                None,
            )  # .srt equivalent in yt-dlp can vary
            if srt_cap:
                transcript_url = srt_cap.get("url")
                logging.info(
                    f"Found English auto-caption URL (format: {srt_cap.get('ext')}): {transcript_url}"
                )
            else:
                # Fallback to the first available format if specific ones aren't found
                transcript_url = en_auto_caps[0].get("url")
                logging.warning(
                    f"SRT/VTT/TTML auto-caption not found, using first available format ({en_auto_caps[0].get('ext')})"
                )

        # Optional: Look for manual subtitles if writesubtitles=True and automatic failed
        # subs = info.get('subtitles', {})
        # en_subs = subs.get('en', [])
        # if not transcript_url and en_subs:
        #     # Similar logic to find SRT/VTT format for manual subs
        #     pass

        if not description and not transcript_url:
            logging.warning(
                f"Could not extract description or transcript URL for {url}"
            )
            # Decide if this is an error or just missing info. Returning empty info for now.
            # return f"Error: Could not extract description or find English transcript URL for {url}"

        return {"description": description, "transcript_url": transcript_url}

    except Exception as e:
        logging.error(f"yt-dlp failed for URL {url}: {e}", exc_info=True)
        return f"Error: Failed to process YouTube URL '{url}'. Reason: {e}"


# Example usage (for testing)
if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=hhMXE9-JUAc"  # Example less likely to have subs readily available

    print(f"\n--- Testing URL: {test_url} ---")
    result1 = fetch_youtube_info(test_url)
    print(result1)
