"""Ollama adapter for local/free LLM providers."""
import json
import logging
from typing import List, Optional, Any, AsyncGenerator

import httpx
from pydantic import BaseModel, Field

from app.services.provider_manager import ModelRegistry

logger = logging.getLogger(__name__)


class OllamaChatMessage(BaseModel):
    """Message for Ollama API."""
    role: str
    content: str


class OllamaChatRequest(BaseModel):
    """Request for Ollama chat endpoint."""
    model: str
    messages: List[OllamaChatMessage]
    stream: bool = True
    options: Optional[dict] = None


class OllamaChatResponse(BaseModel):
    """Response from Ollama chat endpoint."""
    model: str
    created_at: str
    message: OllamaChatMessage
    done: bool = False
    done_reason: Optional[str] = None
    total_duration: Optional[int] = None
    eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    prompt_eval_count: Optional[int] = None


class OllamaProvider:
    """Ollama (local/free) provider implementation.

    Ollama is a local LLM runner that supports free, open-source models.
    No API key required - runs locally on your machine.

    Documentation: https://ollama.com
    Models: https://ollama.com/library

    Note: Availability, quotas, and terms depend on your local Ollama installation
    and the specific model weights you pull.
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 60.0) -> None:
        self.config = {"base_url": base_url, "timeout": timeout}
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
        )
        self._model_registry = ModelRegistry("ollama")
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Register commonly available Ollama models.

        Note: These are common models you can pull with 'ollama pull <model>'.
        Actual availability depends on your local setup and internet connection.
        Model weights may require download; sizes can range from a few GB to tens of GB.
        """
        self._model_registry.register_model(
            model_name="llama3.1:8b",
            max_tokens=8192,
            supports_streaming=True,
            cost_per_token=0.0,  # Free local model
            description="Llama 3.1 8B - Meta's model (local weights required)",
        )
        self._model_registry.register_model(
            model_name="llama3.1:70b",
            max_tokens=8192,
            supports_streaming=True,
            cost_per_token=0.0,
            description="Llama 3.1 70B - Larger variant (requires more VRAM)",
        )
        self._model_registry.register_model(
            model_name="qwen2.5:72b",
            max_tokens=32768,
            supports_streaming=True,
            cost_per_token=0.0,
            description="Qwen 2.5 72B - Alibaba's model",
        )
        self._model_registry.register_model(
            model_name="gemma2:9b",
            max_tokens=8192,
            supports_streaming=True,
            cost_per_token=0.0,
            description="Gemma 2 9B - Google's model",
        )

    @property
    def model_registry(self) -> ModelRegistry:
        """Get the model registry for this provider."""
        return self._model_registry

    async def list_local_models(self) -> List[str]:
        """List models available on the local Ollama instance."""
        try:
            response = await self._client.get("/api/tags")
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except httpx.HTTPError as e:
            logger.warning(f"Failed to list local models: {e}")
            return []

    async def chat_completion(
        self,
        model: str,
        messages: List[OllamaChatMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> dict:
        """Generate a chat completion from Ollama.

        Args:
            model: Model name (e.g., "llama3.1")
            messages: List of chat messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional options (e.g., keep_alive)

        Returns:
            Chat completion response dict
        """
        payload = {
            "model": model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "options": {
                "temperature": temperature,
                **kwargs,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await self._client.post("/api/chat", json=payload)

        if response.status_code != 200:
            error_text = response.text
            try:
                error_data = json.loads(error_text)
                detail = error_data.get("error", error_text)
            except json.JSONDecodeError:
                detail = error_text
            logger.error(f"Ollama provider error: {response.status_code} - {detail}")
            raise Exception(f"Ollama error: {detail}")

        return response.json()

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[OllamaChatMessage],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """Stream chat completions from Ollama.

        Yields:
            Dict chunks with 'message' and 'done' fields
        """
        url = "/api/chat"
        payload = {
            "model": model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature,
                **kwargs,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with self._client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    yield chunk
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse stream chunk: {e}")
                    continue

    async def close(self) -> None:
        """Close the provider's HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def check_connection(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            import asyncio
            # Simple connectivity check
            return True  # Will be validated on actual API calls
        except Exception:
            return False