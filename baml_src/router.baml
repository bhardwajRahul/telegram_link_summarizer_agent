// Define the possible extraction tools
enum ExtractorTool {
  WebpageExtractor // For general webpages
  PDFExtractor     // For PDF documents
  TwitterExtractor // For Twitter/X URLs
  LinkedInExtractor // For LinkedIn post URLs
  Unsupported      // For URLs or content types we cannot handle
}

// Define the router function
// It takes the original message and decides which tool to use.
function RouteRequest(original_message: string) -> ExtractorTool {
  // Use a capable but fast client for routing
//   client Gemini2_5_flash
  client DeepSeekV3

  prompt #"
    Analyze the following user message and determine the best tool to use for extracting content from any URL present.

    User Message:
    ---
    {{ original_message }}
    ---

    Identify the primary URL in the message. Based *only* on the URL's structure or file extension, choose one of the following tools:

    - If the URL points to a PDF file (ends with .pdf), choose PDFExtractor.
    - If the URL is from Twitter or X (contains twitter.com or x.com), choose TwitterExtractor.
    - If the URL is a LinkedIn post (contains linkedin.com/posts/), choose LinkedInExtractor.
    - For all other standard web URLs (http or https), choose WebpageExtractor.
    - If no URL is found, or the URL type is clearly unsupported (e.g., ftp://, mailto:), choose Unsupported.

    Output *only* the name of the chosen tool from the 'ExtractorTool' enum.

    {{ ctx.output_format }}
  "#
}

// Optional test case
test RouteWebpage {
  functions [RouteRequest]
  args {
    original_message #"Summarize this blog post: https://example.com/blog/article-123"#
  }
}

test RoutePDF {
  functions [RouteRequest]
  args {
    original_message #"Can you process this PDF? https://arxiv.org/pdf/2401.0001.pdf"#
  }
}

test RouteTwitter {
  functions [RouteRequest]
  args {
    original_message #"Look at this thread: https://x.com/user/status/12345"#
  }
}

test RouteLinkedIn {
  functions [RouteRequest]
  args {
    original_message #"Interesting thoughts here: https://www.linkedin.com/posts/someuser_activity-1234567890-abcd?utm_source=share"#
  }
}

test RouteNoURL {
  functions [RouteRequest]
  args {
    original_message #"Tell me a joke."#
  }
}

test RouteUnsupported {
  functions [RouteRequest]
  args {
    original_message #"Check this out: ftp://files.example.com/data.zip"#
  }
}

