import requests
import fitz  # PyMuPDF

def get_pdf_text(url: str) -> str:
    """Downloads a PDF from a URL and extracts its text content.

    Args:
        url: The URL of the PDF file.

    Returns:
        The extracted text content of the PDF.
        Returns an error message string if download or processing fails.
    """
    try:
        response = requests.get(url, stream=True, timeout=30) # Add timeout
        response.raise_for_status()  # Raise an exception for bad status codes

        # Check content type to ensure it's a PDF before downloading fully
        content_type = response.headers.get('Content-Type', '').lower()
        if 'application/pdf' not in content_type:
            return f"Error: URL does not point to a PDF file (Content-Type: {content_type})"

        # Read the content into memory
        pdf_content = response.content
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text += page.get_text()

        pdf_document.close()
        return text

    except requests.exceptions.RequestException as e:
        return f"Error downloading PDF: {e}"
    except fitz.errors.FitzError as e: # Catch PyMuPDF specific errors
        return f"Error processing PDF: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# Example usage (optional, for testing):
if __name__ == '__main__':
    # Replace with a valid PDF URL for testing
    test_url = "https://arxiv.org/pdf/1706.03762.pdf" # Example: Attention is All You Need paper
    extracted_text = get_pdf_text(test_url)
    if extracted_text.startswith("Error:"):
        print(extracted_text)
    else:
        print("Successfully extracted text:")
        # Print first 500 characters as a sample
        print(extracted_text[:500] + "...")
