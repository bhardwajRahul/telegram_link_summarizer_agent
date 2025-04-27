
// Define an enum for the type of content being summarized
enum ContentType {
  Webpage
  PDF
  GenericText
}

// Define the structure for the summarization output
class Summary {
  title string @description("A concise and informative title for the summarized content(max 10 words).")
  key_points string[] @description("A list of the most important points or takeaways from the content. (3-5 points)")
  concise_summary string @description("A brief paragraph summarizing the entire content. (50-100 words)")
}

// Define the main summarization function
// This function handles shorter texts directly or uses context for RAG-based summaries.
function SummarizeContent(content: string, contentType: ContentType, context: string?) -> Summary {
  // Specifies the client to use for the LLM call. Assumes an 'openai' client is configured in BAML settings.
  // The model used (e.g., gpt-4-turbo-preview) is typically configured in the BAML client settings or passed via environment variables.
  // client Gemini2_5_flash 
  client DeepSeekV3

  // Prompt definition using BAML's syntax
  prompt #"
    You are an expert summarization engine. Your goal is to provide a clear and concise summary of the given text.

    Content Type: {{ contentType }}
    {% if context %}
    Relevant Context (from RAG):
    ---
    {{ context }}
    ---
    {% endif %}

    Original Content:
    ---
    {{ content }}
    ---

    Based *only* on the provided Original Content {% if context %}and the Relevant Context{% endif %}, generate the answer.

    Format your response strictly as the 'Summary' class structure. Ensure the title, key points, and summary are distinct and accurately reflect the source material. 
    Do not include any information not present in the provided text or context.

    # Instructions
    - If the long is for a paper, you need to explain what the paper is trying to solve and how, in separate sections: 
      '## What is the problem the paper is trying to solve?'
      '## How does the paper attempt to solve the problem?'
    - If it's a blog post or webpage, you have to explain like: 'This post or blog or webpage is about ...'
    - If it's a github repo, you have to explain like: 'This github repo is about ... and tries to solve .... It uses ...'
    
    ----
    {{ ctx.output_format}}
  "#
}

test SummarizeTest {
  functions [SummarizeContent]
  args {
    content #"
      The Urgency of Interpretability
April 2025
In the decade that I have been working on AI, I’ve watched it grow from a tiny academic field to arguably the most important economic and geopolitical issue in the world.  In all that time, perhaps the most important lesson I’ve learned is this: the progress of the underlying technology is inexorable, driven by forces too powerful to stop, but the way in which it happens—the order in which things are built, the applications we choose, and the details of how it is rolled out to society—are eminently possible to change, and it’s possible to have great positive impact by doing so.  We can’t stop the bus, but we can steer it.  In the past I’ve written about the importance of deploying AI in a way that is positive for the world, and of ensuring that democracies build and wield the technology before autocracies do.  Over the last few months, I have become increasingly focused on an additional opportunity for steering the bus: the tantalizing possibility, opened up by some recent advances, that we could succeed at interpretability—that is, in understanding the inner workings of AI systems—before models reach an overwhelming level of power.
    "#
    contentType #"Webpage"#
  }
}
