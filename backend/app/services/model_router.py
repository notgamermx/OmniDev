"""OmniDev's integrated model pool: discovery, ordered fallback and cooldowns."""

import time
from decimal import Decimal, InvalidOperation
import httpx
from app.services.connector_service import load_connectors
from app.services.llm_providers import (
    PROVIDER_BY_ID,
    ProviderError,
    ProviderRateLimitError,
    MissingProviderCredential,
    make_provider,
)

_cooldowns: dict[tuple[str, str], float] = {}


def pool_routes():
    return load_connectors().get("routing", {}).get("pool", {}).get("routes", [])


def configured(provider_id, config):
    if provider_id == "builtin":
        return any(
            configured(r["provider"], config)
            for r in pool_routes()
            if r.get("enabled", True)
        )
    saved = load_connectors()["providers"].get(provider_id, {})
    definition = PROVIDER_BY_ID.get(provider_id)
    if not definition:
        return bool(saved)
    secret = getattr(config, definition.env_key, None) if definition.env_key else None
    key = saved.get("api_key") or (secret.get_secret_value().strip() if secret else "")
    account = saved.get("account_id") or (
        getattr(config, definition.account_id_env, None)
        if definition.account_id_env
        else None
    )
    return (not definition.env_key or bool(key)) and (
        not definition.account_id_env or bool(account)
    )


async def discover_models(provider_id, *, transport=None):
    if provider_id == "builtin":
        return [
            {
                "id": "auto",
                "name": "Automatic · your saved fallback order",
                "free": None,
            }
        ]
    provider = make_provider(provider_id, transport=transport)
    try:
        # Cohere v2 chat uses its separate v1 model listing API.
        url = (
            "https://api.cohere.com/v1/models?endpoint=chat"
            if provider_id == "cohere"
            else "models"
        )
        response = await provider._client.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        models = []
        for item in data.get("data", data.get("models", [])):
            if not isinstance(item, dict):
                continue
            name = item.get("id", item.get("name"))
            if not isinstance(name, str):
                continue
            pricing = item.get("pricing", {})
            free = None
            if "prompt" in pricing and "completion" in pricing:
                try:
                    free = (
                        Decimal(str(pricing["prompt"])) == 0
                        and Decimal(str(pricing["completion"])) == 0
                    )
                except InvalidOperation:
                    free = None
            models.append(
                {
                    "id": name,
                    "name": item.get("name")
                    if isinstance(item.get("name"), str)
                    else name,
                    "free": free,
                }
            )
        return sorted(models, key=lambda m: m["id"])
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise ProviderError(
            "Could not load models. Check the provider key and service; a model ID can also be entered manually."
        ) from exc
    finally:
        await provider.close()


class ModelPool:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport
        self.routes = [
            r
            for r in pool_routes()
            if r.get("enabled", True) and configured(r["provider"], config)
        ]
        if not self.routes:
            raise MissingProviderCredential(
                "Open Models, set up a provider and add a model to the built-in router."
            )

    def candidates(self, model):
        if model != "auto":
            raise ProviderError(
                "The built-in router uses model 'auto'. Choose a provider to select a specific model."
            )
        available = [
            r
            for r in self.routes
            if _cooldowns.get((r["provider"], r["model"]), 0) <= time.monotonic()
        ]
        if not available:
            raise ProviderRateLimitError(
                "All selected models are cooling down. Try again shortly or select another model."
            )
        return available

    async def chat_completion(self, model, **kwargs):
        last = None
        for route in self.candidates(model):
            provider = None
            try:
                provider = make_provider(
                    route["provider"], self.config, transport=self.transport
                )
                provider.max_retries = 0  # Move to the next candidate promptly.
                data = await provider.chat_completion(model=route["model"], **kwargs)
                if (
                    not isinstance(data, dict)
                    or not isinstance(data.get("choices"), list)
                    or not data["choices"]
                ):
                    raise ProviderError("Provider returned an invalid completion")
                return {**data, "routed_provider": route["provider"]}
            except (ProviderError, ValueError, TypeError) as exc:
                last = (
                    exc
                    if isinstance(exc, ProviderError)
                    else ProviderError("Provider returned an invalid response")
                )
                _cooldowns[(route["provider"], route["model"])] = time.monotonic() + (
                    30 if isinstance(exc, ProviderRateLimitError) else 5
                )
            finally:
                if provider:
                    await provider.close()
        raise last or ProviderError("No selected model is available")

    async def chat_completion_stream(self, model, **kwargs):
        last = None
        for route in self.candidates(model):
            provider, emitted = None, False
            try:
                provider = make_provider(
                    route["provider"], self.config, transport=self.transport
                )
                provider.max_retries = 0
                async for chunk in provider.chat_completion_stream(
                    model=route["model"], **kwargs
                ):
                    if not isinstance(chunk, dict) or "error" in chunk:
                        raise ProviderError("Provider returned an invalid stream event")
                    emitted = True
                    yield {**chunk, "routed_provider": route["provider"]}
                return
            except ProviderError as exc:
                _cooldowns[(route["provider"], route["model"])] = time.monotonic() + (
                    30 if isinstance(exc, ProviderRateLimitError) else 5
                )
                if emitted:
                    raise  # Never splice two different model responses together.
                last = exc
            finally:
                if provider:
                    await provider.close()
        raise last or ProviderError("No selected model is available")

    async def close(self):
        pass
