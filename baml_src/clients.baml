client<llm> Gemini2_5_flash {
  provider google-ai
  options {
    model gemini-2.5-flash-preview-04-17
    api_key env.GEMINI_API_KEY
  }
}

client<llm> Gemini2_5_pro {
  provider google-ai
  options {
    model gemini-2.5-pro-exp-03-25
    api_key env.GEMINI_API_KEY
  }
}

client<llm> DeepSeekR1 {
  provider "openai"
  options {
    api_key env.DEEPSEEK_API_KEY
    base_url "https://api.deepseek.com"
    model "deepseek-reasoner"
  }
}

client<llm> DeepSeekV3 {
  provider "openai"
  options {
    api_key env.DEEPSEEK_API_KEY
    base_url "https://api.deepseek.com"
    model "deepseek-chat"
    temperature 0.1
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/fallback
client<llm> LLMFallback {
  provider fallback
  options {
    // This will try the clients in order until one succeeds
    strategy [DeepSeekV3, Gemini2_5_flash]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  // Strategy is optional
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  // Strategy is optional
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}