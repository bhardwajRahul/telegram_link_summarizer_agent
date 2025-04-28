# tools/scrape.py
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

# Selenium Grid URL (will be accessible via Docker Compose service name)
SELENIUM_GRID_URL = os.environ.get("SELENIUM_GRID_URL", "http://selenium:4444/wd/hub")

def find_tweet_article_element(driver):
    """Tries to find the main tweet article container element."""
    # Primarily target the article element
    try:
        # Wait for the article element itself to be present
        article_selector = (By.CSS_SELECTOR, 'article[data-testid="tweet"]')
        wait = WebDriverWait(driver, 10) # Shorter wait for the container
        element = wait.until(EC.presence_of_element_located(article_selector))
        print("Found tweet article element using: css selector article[data-testid='tweet']")
        print(f"Element found: {element}")
        return element
    except (NoSuchElementException, TimeoutException):
        print("Could not find the main tweet article element.")
        return None

def get_page_screenshot_selenium(url: str, timeout: int = 30) -> bytes | str:
    """Fetches a full-page screenshot of a URL via Selenium Remote WebDriver.

    Args:
        url: The URL of the webpage to screenshot.
        timeout: Maximum time in seconds to wait for the page to load.

    Returns:
        bytes | str: Screenshot bytes if successful, error message string if failed.
    """
    driver = None
    screenshot_bytes = None
    try:
        print(f"Initializing Remote WebDriver for screenshot for {url} pointing to {SELENIUM_GRID_URL}...")
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Still run headless in the container
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        # Connect to the Remote WebDriver (Selenium Grid)
        driver = webdriver.Remote(
            command_executor=SELENIUM_GRID_URL,
            options=chrome_options
        )
        driver.set_page_load_timeout(timeout)
        
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for body to be present to ensure page is somewhat loaded
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Page loaded. Taking screenshot...")
        
        # Give a brief moment for rendering
        time.sleep(2) 

        # Take screenshot of the full page
        try:
            # Try to use the full page screenshot method first
            try:
                screenshot_bytes = driver.get_full_page_screenshot_as_png()
                print(f"SUCCESS: Captured full page screenshot ({len(screenshot_bytes)} bytes).")
            except AttributeError:
                # Fallback to standard screenshot if full page not available
                print("Full page screenshot not available, using standard screenshot...")
                screenshot_bytes = driver.get_screenshot_as_png()
                print(f"SUCCESS: Captured standard screenshot ({len(screenshot_bytes)} bytes).")
            
            if not screenshot_bytes:
                return "Error: Failed to capture screenshot (empty bytes)"
                
            return screenshot_bytes

        except Exception as ss_err:
            print(f"ERROR taking screenshot: {ss_err}")
            return f"Error: Screenshot failed: {ss_err}"

    except TimeoutException:
        print(f"Timeout occurred while loading {url} for screenshot")
        return f"Error: Timeout occurred while loading {url} for screenshot"
    except Exception as e:
        print(f"An error occurred during Selenium processing for {url}: {e}")
        return f"Error: An error occurred during Selenium processing: {e}"
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()


def get_page_content_selenium(url: str, timeout: int = 30) -> str:
    """Fetches the text content of a webpage using Selenium Remote WebDriver.

    Args:
        url: The URL of the webpage to scrape.
        timeout: Maximum time in seconds to wait for the page to load.

    Returns:
        str: The extracted text content of the page, or error message if an error occurred.
    """
    driver = None
    page_text = None
    try:
        print(f"Initializing Remote WebDriver for content extraction for {url} pointing to {SELENIUM_GRID_URL}...")
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Still run headless in the container
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        # Connect to the Remote WebDriver (Selenium Grid)
        driver = webdriver.Remote(
            command_executor=SELENIUM_GRID_URL,
            options=chrome_options
        )
        driver.set_page_load_timeout(timeout)
        
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for body to be present
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Page loaded. Extracting text content...")
        
        # Try to find the specific tweet element first
        page_text = None
        try:
            print("Attempting to find tweet article element...")
            tweet_article = find_tweet_article_element(driver)
            if tweet_article:
                time.sleep(2) # Wait for tweet text to potentially load
                print("Extracting text from tweet article element...")
                page_text = tweet_article.text
                if page_text:
                    print(f"SUCCESS: Extracted {len(page_text)} chars from tweet element.")
                else:
                    print("INFO: Tweet article element found, but contained no text. Will try body text.")
            else:
                 print("INFO: Tweet article element not found. Will try body text.")
        except Exception as tweet_find_err:
            print(f"ERROR locating/processing tweet element: {tweet_find_err}. Will try body text.")
            page_text = None
        
        # Simple text extraction from body if tweet element wasn't found/processed
        if not page_text:
            time.sleep(2) # Allow some time for dynamic content
            try:
                print("Extracting text content from body using JS...")
                page_text = driver.execute_script("return document.body.innerText;")
                if page_text:
                    print(f"SUCCESS: Extracted {len(page_text)} chars from body via JS.")
                else:
                    print("INFO: JS extraction returned empty text from body.")
                    
                    # Try one more approach - get all visible text
                    print("Trying to get all visible text...")
                    body = driver.find_element(By.TAG_NAME, "body")
                    page_text = body.text
                    if page_text:
                        print(f"SUCCESS: Extracted {len(page_text)} chars from body.text.")
                    else:
                        return "Error: Could not extract text content from page (all methods failed)"
            except Exception as js_err:
                print(f"ERROR extracting text content via JS: {js_err}")
                return f"Error: Failed to extract text via JavaScript: {js_err}"

        # If we still don't have text at this point, return an error
        if not page_text or not page_text.strip():
            return "Error: No text content could be extracted from the page"
            
        return page_text

    except TimeoutException:
        print(f"Timeout occurred while loading {url}")
        return f"Error: Timeout occurred while loading {url}"
    except Exception as e:
        print(f"An error occurred during Selenium processing for {url}: {e}")
        return f"Error: An error occurred during Selenium processing: {e}"
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()


if __name__ == "__main__":
    # Simple test
    test_url = "https://x.com/Nils_Reimers/status/1915431608980586874"
    print(f"Testing scraping for URL: {test_url}")
    try:
        # Using the new selenium content extraction function
        content = get_page_content_selenium(test_url)
        if content:
             print(f"Successfully retrieved content (first 500 chars):\n{content[:500]}")
        else:
             print("Failed to retrieve content.")
        
        # Optional: Uncomment to test screenshot functionality
        print(f"\nTesting screenshot for URL: {test_url}")
        screenshot_data = get_page_screenshot_selenium(test_url)
        if isinstance(screenshot_data, bytes):
            # Example: Save the screenshot to a file
            try:
                with open("test_screenshot.png", "wb") as f:
                    f.write(screenshot_data)
                print(f"Screenshot saved to: test_screenshot.png ({len(screenshot_data)} bytes)")
            except Exception as write_err:
                print(f"Error saving screenshot: {write_err}")
        else:
            print("Failed to retrieve screenshot.")

    except Exception as e:
        print(f"Error during test: {e}")
