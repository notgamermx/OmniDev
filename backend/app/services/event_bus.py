"""Event bus for application events and messaging."""
import asyncio
import logging
from typing import Callable, Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)


class EventBus:
    """Simple async event bus for decoupled event publishing and subscription."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable]] = {}
        self._pattern_handlers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Subscribe a handler to an event type."""
        async with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug(f"Subscribed handler to event: {event_type}")

    async def unsubscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Unsubscribe a handler from an event type."""
        async with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
                logger.debug(f"Unsubscribed handler from event: {event_type}")

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish an event to all subscribed handlers."""
        async with self._lock:
            handlers = list(self._handlers.get(event_type, []))
            pattern_handlers = list(self._pattern_handlers.get(event_type, []))

        # Execute handlers concurrently
        await asyncio.gather(
            *[handler(payload) for handler in handlers],
            return_exceptions=True,
        )

        # Execute pattern handlers (event_type as substring match)
        for pattern, handlers in self._pattern_handlers.items():
            if pattern in event_type:
                await asyncio.gather(
                    *[handler(payload) for handler in handlers],
                    return_exceptions=True,
                )

    async def subscribe_pattern(self, pattern: str, handler: Callable[[dict], None]) -> None:
        """Subscribe a handler to events matching a pattern (substring)."""
        async with self._lock:
            if pattern not in self._pattern_handlers:
                self._pattern_handlers[pattern] = []
            if handler not in self._pattern_handlers[pattern]:
                self._pattern_handlers[pattern].append(handler)
                logger.debug(f"Subscribed pattern handler for: {pattern}")

    def get_subscribers(self, event_type: str) -> List[Callable]:
        """Get all handlers subscribed to an event type (for debugging)."""
        return self._handlers.get(event_type, [])

    def get_pattern_subscribers(self, pattern: str) -> List[Callable]:
        """Get all pattern handlers matching an event type."""
        return self._pattern_handlers.get(pattern, [])