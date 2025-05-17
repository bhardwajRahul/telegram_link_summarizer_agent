"""
linkedin_agentql_scraper.py

Scrape a public LinkedIn post’s author name and full body text using Playwright + AgentQL.

⚠️  Limitations
    * Works only for *public* posts (i.e. visible to signed‑out visitors).
    * For private / connection‑only posts, you must authenticate first.

Prerequisites:
    pip install playwright agentql
    playwright install
    export AGENTQL_API_KEY=<your AgentQL API key>

Usage:
    python linkedin_agentql_scraper.py --url "https://www.linkedin.com/posts/..." [--headless]

The script prints a JSON‑style dict with keys ``author`` and ``content``.
"""

from __future__ import annotations

import argparse
import os
import textwrap
from dotenv import load_dotenv
import agentql
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()


def scrape_linkedin_post(url: str, headless: bool = True) -> dict[str, str]:
    """Return the post’s author name and full text content."""

    # 0. Configure AgentQL
    agentql.configure(api_key=os.getenv("AGENTQL_API_KEY", ""))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = agentql.wrap(browser.new_page())

        # 1. Navigate & wait for DOM ready
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_page_ready_state()

        # 2. Accept cookies / privacy banner if shown (EU visitors)
        try:
            banner = page.query_elements(
                """
                {
                    accept_cookies_btn
                }
                """
            )
            banner.accept_cookies_btn.click(timeout=3000)
        except Exception:
            # Fallback Locator
            try:
                page.locator("button:has-text('Accept cookies')").click(timeout=3000)
            except PlaywrightTimeoutError:
                pass  # No banner

        # 3. Expand “…see more” inside the post body (if truncated)
        try:
            more = page.query_elements(
                """
                {
                    expand_post_body_btn
                }
                """
            )
            more.expand_post_body_btn.click(timeout=3000)
        except Exception:
            try:
                page.locator("button:has-text('see more')").first.click(timeout=3000)
            except PlaywrightTimeoutError:
                pass

        # 4. Extract author & content via AgentQL
        data = page.query_data(
            """
            {
                author_name
                post_body_text
            }
            """
        )

        browser.close()

        return {
            "author": data.get("author_name", ""),
            "content": textwrap.dedent(data.get("post_body_text", "")).strip(),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape a LinkedIn post via Playwright + AgentQL. Works for public posts only."
    )
    parser.add_argument("--url", required=True, help="Public LinkedIn post URL")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default: GUI).",
    )
    args = parser.parse_args()

    result = scrape_linkedin_post(args.url, headless=args.headless)
    print("\n=== RESULT ===")
    print("Author:", result["author"])
    print("\nPost text:\n", result["content"])
