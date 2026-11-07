"""Base provider interface and registry for AI model providers."""
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator, Type

logger = logging.getLogger(__name__)


class BaseProvider:
    """Abstract base class for AI model providers.

    All provider adapters must implement this interface so the application
    can use them interchangeably.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.config = kwargs

    @property
    def model_registry(self) -> Any:
        """Return the model registry for this provider."""
        raise NotImplementedError("Subclasses must implement model_registry")

    async def chat_completion(
        self,
        model: str,
        messages: List[dict],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict:
        """Generate a chat completion.

        Args:
            model: Model name to use
            messages: List of chat messages (dict with 'role' and 'content')
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional provider-specific parameters

        Returns:
            Chat completion response dict
        """
        raise NotImplementedError("Subclasses must implement chat_completion")

    async def chat_completion_stream(
        self,
        model: str,
        messages: List[dict],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """Stream a chat completion.

        Yields:
            Dict chunks with streaming data
        """
        raise NotImplementedError("Subclasses must implement chat_completion_stream")

    async def close(self) -> None:
        """Close the provider's HTTP client and resources."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


class ProviderRegistry:
    """Registry for managing AI model providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, Type[BaseProvider]] = {}
        self._instances: Dict[str, BaseProvider] = {}
        self._default_provider: Optional[str] = None

    def register(self, name: str, provider_class: Type[BaseProvider], default: bool = False) -> None:
        """Register a provider class.

        Args:
            name: Provider name (e.g., 'openai', 'ollama')
            provider_class: Provider class implementing BaseProvider
            default: Whether this is the default provider
        """
        self._providers[name] = provider_class
        if default or self._default_provider is None:
            self._default_provider = name
        logger.info(f"Registered provider: {name}")

    def get_provider_class(self, name: Optional[str] = None) -> Optional[Type[BaseProvider]]:
        """Get a provider class by name."""
        name = name or self._default_provider
        return self._providers.get(name)

    def get_provider(self, name: Optional[str] = None) -> Optional[BaseProvider]:
        """Get a provider instance by name."""
        name = name or self._default_provider
        return self._instances.get(name)

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

    async def create_provider(self, name: str, **kwargs: Any) -> BaseProvider:
        """Create a provider instance.

        Args:
            name: Provider name
            **kwargs: Arguments to pass to provider constructor

        Returns:
            Provider instance
        """
        provider_class = self.get_provider_class(name)
        if not provider_class:
            raise ValueError(f"Provider {name} not registered")
        instance = provider_class(**kwargs)
        self._instances[name] = instance
        return instance

    async def close_all(self) -> None:
        """Close all provider instances."""
        for instance in self._instances.values():
            try:
                await instance.close()
            except Exception as e:
                logger.warning(f"Error closing provider {instance.name}: {e}")
        self._instances.clear()

    @property
    def default_provider(self) -> Optional[str]:
        """Get the default provider name."""
        return self._default_provider


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def register_provider(name: str, provider_class: Type[BaseProvider], default: bool = False) -> None:
    """Convenience function to register a provider."""
    get_provider_registry().register(name, provider_class, default)


def set_default_provider(name: str) -> None:
    """Convenience function to set the default provider."""
    get_provider_registry().set_default(name)