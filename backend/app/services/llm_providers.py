"""Provider catalog and small shared adapters for chat-completion APIs."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import random
from typing import Any, AsyncIterator

import httpx

from app.core.config import Settings, settings


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    category: str
    base_url: str
    env_key: str | None
    api_style: str
    free_access: str
    docs_url: str
    connect_url: str
    account_id_env: str | None = None


PROVIDERS = (
    ProviderDefinition("google_gemini", "Google Gemini", "cloud", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "openai_compatible", "free_tier", "https://ai.google.dev/gemini-api/docs", "https://aistudio.google.com/apikey"),
    ProviderDefinition("groq", "Groq", "cloud", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai_compatible", "free_tier", "https://console.groq.com/docs", "https://console.groq.com/keys"),
    ProviderDefinition("openrouter", "OpenRouter", "aggregator", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openai_compatible", "free_models_available", "https://openrouter.ai/docs", "https://openrouter.ai/settings/keys"),
    ProviderDefinition("ollama", "Ollama", "local", "http://localhost:11434/v1", None, "openai_compatible", "fully_local_free", "https://docs.ollama.com/", "https://ollama.com/download"),
    ProviderDefinition("mistral", "Mistral AI", "cloud", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "openai_compatible", "check_current_plan", "https://docs.mistral.ai/", "https://console.mistral.ai/api-keys/"),
    ProviderDefinition("cloudflare", "Cloudflare Workers AI", "cloud", "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1", "CLOUDFLARE_API_TOKEN", "openai_compatible", "daily_free_allowance", "https://developers.cloudflare.com/workers-ai/", "https://dash.cloudflare.com/", "CLOUDFLARE_ACCOUNT_ID"),
    ProviderDefinition("cohere", "Cohere", "cloud", "https://api.cohere.com/v2", "COHERE_API_KEY", "native", "trial_limited", "https://docs.cohere.com/", "https://dashboard.cohere.com/api-keys"),
    ProviderDefinition("nvidia_nim", "NVIDIA NIM", "cloud", "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY", "openai_compatible", "free_developer_credits_check", "https://docs.api.nvidia.com/nim/", "https://build.nvidia.com/"),
    ProviderDefinition("cerebras", "Cerebras", "cloud", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "openai_compatible", "free_tier", "https://inference-docs.cerebras.ai/", "https://cloud.cerebras.ai/"),
    ProviderDefinition("huggingface", "Hugging Face Inference Providers", "aggregator", "https://router.huggingface.co/v1", "HF_TOKEN", "openai_compatible", "monthly_free_credits", "https://huggingface.co/docs/inference-providers/", "https://huggingface.co/settings/tokens"),
    ProviderDefinition("deepinfra", "DeepInfra", "cloud", "https://api.deepinfra.com/v1/openai", "DEEPINFRA_API_KEY", "openai_compatible", "check_current_pricing", "https://docs.deepinfra.com/", "https://deepinfra.com/dash/api_keys"),
    ProviderDefinition("together_ai", "Together AI", "cloud", "https://api.together.xyz/v1", "TOGETHER_API_KEY", "openai_compatible", "check_trial_credits", "https://docs.together.ai/", "https://api.together.ai/settings/api-keys"),
    ProviderDefinition("sambanova", "SambaNova Cloud", "cloud", "https://api.sambanova.ai/v1", "SAMBANOVA_API_KEY", "openai_compatible", "payment_method_or_credits", "https://docs.sambanova.ai/", "https://cloud.sambanova.ai/"),
    ProviderDefinition("openai", "OpenAI", "cloud", "https://api.openai.com/v1", "OPENAI_API_KEY", "openai_compatible", "paid_or_trial", "https://platform.openai.com/docs/", "https://platform.openai.com/api-keys"),
)

PROVIDER_BY_ID = {provider.id: provider for provider in PROVIDERS}


class ProviderError(Exception):
    """Sanitized provider error suitable for mapping to an API response."""


class ProviderRateLimitError(ProviderError):
    pass


class MissingProviderCredential(ProviderError):
    pass


def _retry_after(value: str | None, attempt: int) -> float:
    if value:
        try:
            return min(30.0, max(0.0, float(value)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return min(30.0, max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(30.0, (0.5 * (2**attempt)) + random.uniform(0.0, 0.2))


class OpenAICompatibleProvider:
    def __init__(
        self,
        definition: ProviderDefinition,
        api_key: str | None,
        *,
        account_id: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 2,
    ) -> None:
        if definition.env_key and not api_key:
            raise MissingProviderCredential(f"Configure {definition.env_key} to use {definition.name}")
        if definition.account_id_env and not account_id:
            raise MissingProviderCredential(f"Configure {definition.account_id_env} to use {definition.name}")
        base_url = definition.base_url.format(account_id=account_id or "")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.definition = definition
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            headers=headers,
            transport=transport,
            trust_env=transport is None,
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(path, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise ProviderError("Provider connection failed") from exc
                await asyncio.sleep(_retry_after(None, attempt))
                continue
            if response.status_code == 429 and attempt < self.max_retries:
                await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                continue
            if response.status_code == 429:
                raise ProviderRateLimitError("Provider rate limit exceeded")
            if response.is_error:
                raise ProviderError(f"Provider returned HTTP {response.status_code}")
            return response
        raise ProviderError("Provider request failed")

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = {"model": model, "messages": messages, "temperature": temperature, **kwargs}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        response = await self._post("chat/completions", payload)
        return response.json()

    async def chat_completion_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = {"model": model, "messages": messages, "temperature": temperature, "stream": True, **kwargs}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        for attempt in range(self.max_retries + 1):
            emitted = False
            try:
                async with self._client.stream("POST", "chat/completions", json=payload) as response:
                    if response.status_code == 429 and attempt < self.max_retries:
                        await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                        continue
                    if response.status_code >= 500 and attempt < self.max_retries:
                        await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                        continue
                    if response.status_code == 429:
                        raise ProviderRateLimitError("Provider rate limit exceeded")
                    if response.is_error:
                        raise ProviderError(f"Provider returned HTTP {response.status_code}")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError as exc:
                            raise ProviderError("Provider returned an invalid stream event") from exc
                        emitted = True
                        yield chunk
                return
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if emitted or attempt >= self.max_retries:
                    raise ProviderError("Provider stream connection failed") from exc
                await asyncio.sleep(_retry_after(None, attempt))

    async def close(self) -> None:
        await self._client.aclose()


class CohereProvider(OpenAICompatibleProvider):
    """Cohere's native v2 chat API, normalized to the common chat shape."""

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], temperature: float = 1.0, max_tokens: int | None = None, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, **kwargs}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        response = await self._post("chat", payload)
        data = response.json()
        content = data.get("message", {}).get("content", [])
        text = "".join(item.get("text", "") for item in content if item.get("type") == "text")
        tokens = data.get("usage", {}).get("tokens", {})
        prompt_tokens = tokens.get("input_tokens", 0)
        completion_tokens = tokens.get("output_tokens", 0)
        return {
            "id": data.get("id", ""),
            "object": "chat.completion",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": data.get("finish_reason")}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
        }

    async def chat_completion_stream(self, model: str, messages: list[dict[str, Any]], temperature: float = 1.0, max_tokens: int | None = None, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, "stream": True, **kwargs}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async for event in self._cohere_events(payload):
            yield event

    def _cohere_events(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        async def events() -> AsyncIterator[dict[str, Any]]:
            for attempt in range(self.max_retries + 1):
                emitted = False
                try:
                    async with self._client.stream("POST", "chat", json=payload) as response:
                        if response.status_code == 429 and attempt < self.max_retries:
                            await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                            continue
                        if response.status_code >= 500 and attempt < self.max_retries:
                            await asyncio.sleep(_retry_after(response.headers.get("Retry-After"), attempt))
                            continue
                        if response.status_code == 429:
                            raise ProviderRateLimitError("Provider rate limit exceeded")
                        if response.is_error:
                            raise ProviderError(f"Provider returned HTTP {response.status_code}")
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            try:
                                data = json.loads(line[5:].strip())
                            except json.JSONDecodeError as exc:
                                raise ProviderError("Provider returned an invalid stream event") from exc
                            event_type = data.get("type")
                            if event_type == "content-delta":
                                text = data.get("delta", {}).get("message", {}).get("content", {}).get("text", "")
                                emitted = True
                                yield {"id": data.get("id", ""), "object": "chat.completion.chunk", "created": int(datetime.now(timezone.utc).timestamp()), "model": payload["model"], "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]}
                            elif event_type == "message-end":
                                emitted = True
                                yield {"id": data.get("id", ""), "object": "chat.completion.chunk", "created": int(datetime.now(timezone.utc).timestamp()), "model": payload["model"], "choices": [{"index": 0, "delta": {}, "finish_reason": data.get("delta", {}).get("finish_reason")}]}
                    return
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if emitted or attempt >= self.max_retries:
                        raise ProviderError("Provider stream connection failed") from exc
                    await asyncio.sleep(_retry_after(None, attempt))
        return events()


def has_provider(provider_id: str) -> bool:
    from app.services.connector_service import load_connectors
    return provider_id in PROVIDER_BY_ID or provider_id in load_connectors()["providers"]


def make_provider(provider_id: str, config: Settings = settings, *, transport: httpx.AsyncBaseTransport | None = None) -> OpenAICompatibleProvider:
    definition = PROVIDER_BY_ID.get(provider_id)
    if definition is None:
        from app.services.connector_service import load_connectors
        connection = load_connectors()["providers"].get(provider_id)
        if connection is None:
            raise KeyError(provider_id)
        definition = ProviderDefinition(provider_id, connection["name"], "connector", connection["base_url"], None,
                                        "openai_compatible", "check_gateway_plan", "", "")
        return OpenAICompatibleProvider(definition, connection.get("api_key") or None, transport=transport)
    credential = getattr(config, definition.env_key) if definition.env_key else None
    api_key = credential.get_secret_value().strip() or None if credential else None
    account_id = getattr(config, definition.account_id_env) if definition.account_id_env else None
    provider_type = CohereProvider if definition.api_style == "native" else OpenAICompatibleProvider
    if provider_id == "openai" or provider_id in config.PROVIDER_URLS:
        from dataclasses import replace
        definition = replace(definition, base_url=config.PROVIDER_URLS.get(provider_id, config.OPENAI_BASE_URL))
    return provider_type(definition, api_key, account_id=account_id, transport=transport)
