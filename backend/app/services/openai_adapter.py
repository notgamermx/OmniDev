"""OpenAI-compatible adapter for OmniDev."""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncGenerator

import httpx
from pydantic import BaseModel, Field

from app.services.provider_manager import ProviderManager, ModelRegistry, ModelInfo, get_provider_manager

logger = logging.getLogger(__name__)


# OpenAI-compatible response models
class ChatMessage(BaseModel):
    """A chat message."""
    role: str = Field(..., description="Role of the message author")
    content: str = Field(..., description="Content of the message")


class Choice(BaseModel):
    """A choice in a chat completion response."""
    index: int = Field(..., description="Index of the choice")
    message: ChatMessage = Field(..., description="The chat message")
    finish_reason: Optional[str] = Field(None, description="Reason for finishing")

    # For backwards compatibility with older OpenAI API versions
    text: Optional[str] = Field(None, description="Deprecated. Use message.content instead")


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total number of tokens")

    # Alias for backwards compatibility
    @property
    def total(self) -> int:
        return self.total_tokens


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field("chat.completion", description="Object type")
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="Model name used")
    choices: List[Choice] = Field(..., description="List of choices")
    usage: Usage = Field(..., description="Token usage information")


class ChatCompletionStreamChoice(BaseModel):
    """A choice in a streaming chat completion response."""
    index: int = Field(..., description="Index of the choice")
    delta: ChatMessage = Field(..., description="Delta to add to the message")
    finish_reason: Optional[str] = Field(None, description="Reason for finishing")


class ChatCompletionStreamResponse(BaseModel):
    """OpenAI-compatible streaming chat completion response."""
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Unix timestamp of completion")
    model: str = Field(..., description="Model name used")
    choices: List[ChatCompletionStreamChoice] = Field(..., description="List of choices")


class ProviderConfig(BaseModel):
    """Provider configuration for API keys and endpoints."""
    api_key: str = Field(..., description="API authentication key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for the provider API",
    )
    timeout: float = Field(
        default=60.0,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )


class OpenAIProvider:
    """OpenAI-compatible API provider implementation."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )
        self._model_registry = ModelRegistry("openai")

        # Register default OpenAI models
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Register default OpenAI models."""
        self._model_registry.register_model(
            model_name="gpt-4o",
            max_tokens=128_000,
            supports_streaming=True,
            cost_per_token=0.00003,
            description="GPT-4o (Oct 2023)",
        )
        self._model_registry.register_model(
            model_name="gpt-4-turbo",
            max_tokens=128_000,
            supports_streaming=True,
            cost_per_token=0.00001,
            description="GPT-4o mini (Jan 2024)",
        )
        self._model_registry.register_model(
            model_name="gpt-3.5-turbo",
            max_tokens=16_000,
            supports_streaming=True,
            cost_per_token=0.000001,
            description="GPT-3.5 Turbo (Jan 2024)",
        )

    @property
    def model_registry(self) -> ModelRegistry:
        """Get the model registry for this provider."""
        return self._model_registry

    async def chat_completion(
        self,
        model: str,
        messages: List[ChatMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> ChatCompletionResponse:
        """Generate a chat completion.

        Args:
            model: Model name to use
            messages: List of chat messages
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional provider-specific parameters

        Returns:
            ChatCompletionResponse
        """
        # Validate model exists
        model_info = self._model_registry.get_model(model)
        if not model_info:
            available = self._model_registry.list_model_names()
            raise ValueError(
                f"Model {model} not found. Available: {available}"
            )

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs,
        }

        response = await self._client.post(
            "/chat/completions",
            json=payload,
        )

        if response.status_code != 200:
            logger.error(
                f"Provider error: {response.status_code} - {response.text}"
            )
            raise Exception(f"Provider error: {response.status_code}")

        data = response.json()
        return ChatCompletionResponse(**data)

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[ChatMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Stream a chat completion.

        Args:
            model: Model name to use
            messages: List of chat messages
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            ChatCompletionStreamResponse chunks
        """
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        yield ChatCompletionStreamResponse(
                            id="",
                            object="chat.completion.chunk",
                            created=0,
                            model=model,
                            choices=[],
                        )
                        continue

                    try:
                        chunk = ChatCompletionStreamResponse(**json.loads(chunk_data))
                        yield chunk
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse stream chunk: {e}")
                        continue

    async def close(self) -> None:
        """Close the provider's HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OpenAIProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Async context manager exit."""
        await self.close()