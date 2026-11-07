import json

import httpx
import pytest

from app.services.llm_providers import (
    CohereProvider,
    MissingProviderCredential,
    OpenAICompatibleProvider,
    PROVIDERS,
    PROVIDER_BY_ID,
)


EXPECTED_PROVIDER_IDS = {
    "google_gemini", "groq", "openrouter", "ollama", "mistral", "cloudflare",
    "cohere", "nvidia_nim", "cerebras", "huggingface", "deepinfra", "together_ai",
    "sambanova", "openai",
}


def _completion():
    return {
        "id": "test-response",
        "model": "test-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("definition", [p for p in PROVIDERS if p.api_style == "openai_compatible"], ids=lambda p: p.id)
async def test_each_openai_compatible_provider_sends_chat_request(definition):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_completion())

    provider_type = OpenAICompatibleProvider
    provider = provider_type(
        definition,
        "test-token" if definition.env_key else None,
        account_id="test-account",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await provider.chat_completion("test-model", [{"role": "user", "content": "hello"}])
    finally:
        await provider.close()

    assert result["choices"][0]["message"]["content"] == "ok"
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.path.endswith("/chat/completions")
    if definition.env_key:
        assert seen[0].headers["authorization"] == "Bearer test-token"
    else:
        assert "authorization" not in seen[0].headers
    if definition.id == "cloudflare":
        assert "/accounts/test-account/" in seen[0].url.path


def test_catalog_contains_every_requested_provider():
    assert EXPECTED_PROVIDER_IDS <= set(PROVIDER_BY_ID)
    assert PROVIDER_BY_ID["cohere"].api_style == "native"


def test_missing_credentials_are_rejected():
    with pytest.raises(MissingProviderCredential):
        OpenAICompatibleProvider(PROVIDER_BY_ID["google_gemini"], None)
    with pytest.raises(MissingProviderCredential):
        OpenAICompatibleProvider(PROVIDER_BY_ID["cloudflare"], "token")


@pytest.mark.asyncio
async def test_cohere_v2_native_request_is_normalized():
    def handler(request):
        assert request.url.path == "/v2/chat"
        assert request.headers["authorization"] == "Bearer cohere-token"
        return httpx.Response(200, json={
            "id": "cohere-id",
            "finish_reason": "COMPLETE",
            "message": {"content": [{"type": "text", "text": "hello"}]},
            "usage": {"tokens": {"input_tokens": 4, "output_tokens": 2}},
        })

    provider = CohereProvider(PROVIDER_BY_ID["cohere"], "cohere-token", transport=httpx.MockTransport(handler))
    try:
        result = await provider.chat_completion("command-test", [{"role": "user", "content": "hi"}])
    finally:
        await provider.close()
    assert result["choices"][0]["message"]["content"] == "hello"
    assert result["usage"]["total_tokens"] == 6


@pytest.mark.asyncio
async def test_rate_limit_retry_respects_retry_after(monkeypatch):
    calls = 0
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.services.llm_providers.asyncio.sleep", fake_sleep)

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=_completion())

    provider = OpenAICompatibleProvider(
        PROVIDER_BY_ID["groq"], "test-token", transport=httpx.MockTransport(handler), max_retries=1
    )
    try:
        result = await provider.chat_completion("test-model", [{"role": "user", "content": "hi"}])
    finally:
        await provider.close()
    assert result["id"] == "test-response"
    assert calls == 2
    assert delays == [0.0]


@pytest.mark.asyncio
async def test_openai_compatible_stream_parses_json_sse():
    body = "data: {\"id\":\"s1\",\"choices\":[{\"delta\":{\"content\":\"hi\"}}]}\n\ndata: [DONE]\n\n"
    provider = OpenAICompatibleProvider(
        PROVIDER_BY_ID["google_gemini"], "test-token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)),
    )
    try:
        chunks = [chunk async for chunk in provider.chat_completion_stream("gemini-test", [{"role": "user", "content": "hi"}])]
    finally:
        await provider.close()
    assert chunks == [{"id": "s1", "choices": [{"delta": {"content": "hi"}}]}]


@pytest.mark.asyncio
async def test_cohere_stream_normalizes_content_delta():
    event = {"type": "content-delta", "id": "c1", "delta": {"message": {"content": {"text": "hello"}}}}
    body = f"event: content-delta\ndata: {json.dumps(event)}\n\nevent: stream-end\ndata: {{}}\n\n"
    provider = CohereProvider(
        PROVIDER_BY_ID["cohere"], "token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)),
    )
    try:
        chunks = [chunk async for chunk in provider.chat_completion_stream("command-test", [{"role": "user", "content": "hi"}])]
    finally:
        await provider.close()
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"
