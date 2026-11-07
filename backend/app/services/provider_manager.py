"""Provider Manager for managing AI model providers."""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Type

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages AI model providers and their configurations."""

    def __init__(self) -> None:
        self._providers: Dict[str, Type] = {}
        self._model_registries: Dict[str, "ModelRegistry"] = {}
        self._default_provider: Optional[str] = None

    def register_provider(
        self,
        name: str,
        provider_class: Type,
        model_registry: "ModelRegistry",
        default: bool = False,
    ) -> None:
        """Register a new AI provider.

        Args:
            name: Unique provider name (e.g., "openai", "anthropic")
            provider_class: Provider class implementing the provider interface
            model_registry: ModelRegistry instance for this provider
            default: Whether this is the default provider
        """
        self._providers[name] = provider_class
        self._model_registries[name] = model_registry
        if default or self._default_provider is None:
            self._default_provider = name
        logger.info(f"Registered provider: {name}")

    def get_provider(self, name: Optional[str] = None) -> Optional[Type]:
        """Get a provider class by name.

        Args:
            name: Provider name. Uses default if None.

        Returns:
            Provider class or None if not found
        """
        name = name or self._default_provider
        return self._providers.get(name)

    def get_model_registry(self, name: Optional[str] = None) -> Optional["ModelRegistry"]:
        """Get a model registry by provider name."""
        name = name or self._default_provider
        return self._model_registries.get(name)

    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def set_default(self, name: str) -> None:
        """Set the default provider."""
        if name in self._providers:
            self._default_provider = name
            logger.info(f"Set default provider: {name}")
        else:
            raise ValueError(f"Provider {name} not registered")

    async def create_provider_instance(
        self, name: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """Create a provider instance.

        Args:
            name: Provider name. Uses default if None.
            **kwargs: Arguments to pass to provider constructor.

        Returns:
            Provider instance
        """
        provider_class = self.get_provider(name)
        if not provider_class:
            raise ValueError(f"Provider {name or self._default_provider} not registered")
        return provider_class(**kwargs)


class ModelInfo:
    """Information about a model available from a provider."""

    def __init__(
        self,
        name: str,
        provider: str,
        max_tokens: int,
        supports_streaming: bool = True,
        cost_per_token: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        self.name = name
        self.provider = provider
        self.max_tokens = max_tokens
        self.supports_streaming = supports_streaming
        self.cost_per_token = cost_per_token
        self.description = description

    def __repr__(self) -> str:
        return f"ModelInfo(name={self.name}, provider={self.provider})"


class ModelRegistry:
    """Registry of available models for a provider."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self._models: Dict[str, ModelInfo] = {}

    def register_model(
        self,
        model_name: str,
        max_tokens: int,
        supports_streaming: bool = True,
        cost_per_token: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        """Register a model with the provider."""
        model_info = ModelInfo(
            name=model_name,
            provider=self.provider_name,
            max_tokens=max_tokens,
            supports_streaming=supports_streaming,
            cost_per_token=cost_per_token,
            description=description,
        )
        self._models[model_name] = model_info
        logger.debug(f"Registered model: {model_name}")

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get model info by name."""
        return self._models.get(model_name)

    def list_models(self) -> List[ModelInfo]:
        """List all registered models."""
        return list(self._models.values())

    def list_model_names(self) -> List[str]:
        """List all registered model names."""
        return list(self._models.keys())


# Global provider manager instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager


def register_provider(
    name: str,
    provider_class: Type,
    model_registry: ModelRegistry,
    default: bool = False,
) -> None:
    """Convenience function to register a provider."""
    get_provider_manager().register_provider(name, provider_class, model_registry, default)


def set_default_provider(name: str) -> None:
    """Convenience function to set the default provider."""
    get_provider_manager().set_default(name)