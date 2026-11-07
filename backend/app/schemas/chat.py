"""Pydantic schemas for LLM chat endpoints."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Chat message roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessageSchema(BaseModel):
    """A chat message in a conversation."""
    role: Role = Field(..., description="Role of the message author")
    content: str = Field(..., description="Content of the message")
    name: Optional[str] = Field(None, description="Name of the contributor")


class ChatCompletionRequest(BaseModel):
    """Request body for chat completion endpoint."""
    provider: str = Field(..., description="AI provider name (e.g., 'openai', 'anthropic')")
    model: str = Field(..., description="Model name to use")
    messages: List[ChatMessageSchema] = Field(
        ...,
        description="List of messages in the conversation"
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0-2)"
    )
    max_tokens: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum tokens to generate"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response"
    )


class ChoiceSchema(BaseModel):
    """A choice in a chat completion response."""
    index: int = Field(..., description="Index of the choice")
    message: ChatMessageSchema = Field(..., description="The chat message")
    finish_reason: Optional[str] = Field(None, description="Reason for finishing")


class UsageSchema(BaseModel):
    """Token usage information."""
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total number of tokens")


class ChatCompletionResponseSchema(BaseModel):
    """Response schema for chat completion."""
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp()),
        description="Unix timestamp of creation"
    )
    model: str = Field(..., description="Model name used")
    provider: str = Field(..., description="Provider that generated the response")
    choices: List[ChoiceSchema] = Field(..., description="List of choices")
    usage: UsageSchema = Field(..., description="Token usage information")


class ChatCompletionStreamChunkSchema(BaseModel):
    """Schema for a streaming chunk response."""
    id: str = Field(..., description="Unique identifier for the response")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Unix timestamp of chunk")
    model: str = Field(..., description="Model name used")
    provider: str = Field(..., description="Provider that generated the chunk")
    choices: List[dict] = Field(..., description="List of chunk choices")


class ProviderInfo(BaseModel):
    """Information about an AI provider."""
    name: str = Field(..., description="Provider name")
    category: str
    api_style: str
    free_access: str = Field(description="Provider tier label; check the provider for current terms and quotas")
    docs_url: str
    connect_url: str
    env_key: Optional[str] = None
    configured: bool


class ModelInfoSchema(BaseModel):
    """Information about a model."""
    name: str = Field(..., description="Model name")
    provider: str = Field(..., description="Provider that offers this model")
    max_tokens: int = Field(..., description="Maximum context length")
    supports_streaming: bool = Field(..., description="Whether model supports streaming")
    cost_per_token: Optional[float] = Field(None, description="Cost per token (if known)")
    description: Optional[str] = Field(None, description="Model description")


class ErrorDetail(BaseModel):
    """Error response schema."""
    detail: str = Field(..., description="Error description")
    error_type: Optional[str] = Field(None, description="Error type for categorization")
