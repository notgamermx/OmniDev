"""Multi-provider chat endpoints."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.chat import ChatCompletionRequest, ProviderInfo
from app.services.llm_providers import (
    PROVIDERS,
    has_provider,
    MissingProviderCredential,
    ProviderError,
    ProviderRateLimitError,
    make_provider,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _configured(provider_id: str) -> bool:
    from app.services.model_router import configured
    return configured(provider_id, settings)


def _normalize_completion(data: dict[str, Any], provider_id: str, model: str) -> dict[str, Any]:
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    return {
        "id": data.get("id", ""),
        "model": data.get("model", model),
        "provider": provider_id,
        **({"routed_provider": data["routed_provider"]} if "routed_provider" in data else {}),
        "choices": [{
            "index": choice.get("index", 0),
            "message": choice.get("message", {"role": "assistant", "content": ""}),
            "finish_reason": choice.get("finish_reason"),
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0),
        },
    }


@router.get("/providers/", response_model=list[ProviderInfo], summary="List supported AI providers")
async def list_providers() -> list[ProviderInfo]:
    builtins = [
        ProviderInfo(
            name=provider.id,
            display_name=provider.name,
            category=provider.category,
            api_style=provider.api_style,
            free_access=provider.free_access,
            docs_url=provider.docs_url,
            connect_url=provider.connect_url,
            env_key=provider.env_key,
            configured=_configured(provider.id),
        )
        for provider in PROVIDERS
    ]
    from app.services.connector_service import load_connectors
    integrated = ProviderInfo(name="builtin", display_name="OmniDev · built-in router", category="builtin", api_style="openai_compatible", free_access="your_selected_models", docs_url="", connect_url="", configured=_configured("builtin"))
    return [integrated] + builtins + [ProviderInfo(name=name, display_name=value["name"], category="connector", api_style="openai_compatible",
        free_access="check_gateway_plan", docs_url="", connect_url="", configured=True)
        for name, value in load_connectors()["providers"].items() if name.startswith("custom_")]


@router.post("/completions/", summary="Create a chat completion")
async def chat_completion(request: ChatCompletionRequest) -> dict[str, Any]:
    if not has_provider(request.provider):
        raise HTTPException(status_code=404, detail="Unknown provider")
    if request.stream:
        raise HTTPException(status_code=400, detail="Use /completions/stream for streaming responses")
    try:
        provider = make_provider(request.provider)
    except MissingProviderCredential as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown provider") from exc

    try:
        messages = [message.model_dump(mode="json", exclude_none=True) for message in request.messages]
        result = await provider.chat_completion(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return _normalize_completion(result, request.provider, request.model)
    except ProviderRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected chat failure for provider %s", request.provider)
        raise HTTPException(status_code=502, detail="Provider request failed") from exc
    finally:
        await provider.close()


@router.post("/completions/stream", summary="Stream a chat completion")
async def chat_completion_stream(request: ChatCompletionRequest) -> StreamingResponse:
    if not has_provider(request.provider):
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        provider = make_provider(request.provider)
    except MissingProviderCredential as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown provider") from exc

    messages = [message.model_dump(mode="json", exclude_none=True) for message in request.messages]

    async def events():
        try:
            async for chunk in provider.chat_completion_stream(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"
            yield "data: [DONE]\n\n"
        except ProviderError as exc:
            yield f"data: {json.dumps({'error': {'detail': str(exc)}})}\n\n"
        except Exception:
            logger.exception("Unexpected streaming failure for provider %s", request.provider)
            yield 'data: {"error":{"detail":"Provider stream failed"}}\n\n'
        finally:
            await provider.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
