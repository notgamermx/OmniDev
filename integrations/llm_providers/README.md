# LLM providers

The API exposes a common chat-completions interface at `/api/v1/chat/completions/` and `/api/v1/chat/completions/stream`. Select a provider and its model ID in each request. Most providers use the OpenAI-compatible chat API; Cohere is handled using its native v2 chat endpoint.

Supported IDs: `google_gemini`, `groq`, `openrouter`, `ollama`, `mistral`, `cloudflare`, `cohere`, `nvidia_nim`, `cerebras`, `huggingface`, `deepinfra`, `together_ai`, `sambanova`, and `openai`.

Copy `.env.example` to `.env`, then set only the credentials for providers you use. The Cloudflare adapter also requires `CLOUDFLARE_ACCOUNT_ID`. Ollama is local and does not use an API key. Credentials are read as secret settings and are not included in provider-list responses.

Use `GET /api/v1/chat/providers/` to see provider IDs, documentation links, key names, and whether credentials are configured. The request `model` must be a model ID accepted by the selected provider; model availability is provider/account-specific.

The provider catalog records free-access notes from the project’s provider list. Treat these as hints only: free access, credits, prices, quotas, and terms can change and must be checked with the provider. No live provider call is part of the test suite.

Run mocked provider tests with `python -m pytest backend/tests/test_llm_providers.py backend/tests/test_llm_api.py -v`.
