"""Context manager with token-aware compaction for agent execution."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Represents a token-managed context window."""
    _messages: List[Dict[str, Any]] = field(default_factory=list)
    max_tokens: int = 16000  # Default model context window
    reserved_tokens: int = 2000  # Reserve for response generation

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Get the message list."""
        return self._messages

    @property
    def available_tokens(self) -> int:
        return max(0, self.max_tokens - self.reserved_tokens - self.current_tokens)

    @property
    def current_tokens(self) -> int:
        return sum(self._estimate_tokens(msg) for msg in self._messages)

    def _estimate_tokens(self, message: Dict[str, Any]) -> int:
        """Rough token estimation (4 chars ~ 1 token)."""
        content = message.get("content", "")
        if isinstance(content, str):
            return len(content) // 4 + 10  # +10 for role overhead
        return 10

    def append(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Append a message to the context window."""
        self._messages.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def to_list(self) -> List[Dict[str, str]]:
        """Return messages as a list of role/content dicts."""
        return [{"role": m["role"], "content": m["content"]} for m in self._messages]


class ContextManager:
    """Manages conversation context with automatic compaction."""

    def __init__(
        self,
        max_tokens: int = 16000,
        reserved_tokens: int = 2000,
        compaction_window: int = 5,
        preserve_first_n: int = 2
    ):
        self.max_tokens = max_tokens
        self.reserved_tokens = reserved_tokens
        self.compaction_window = compaction_window
        self.preserve_first_n = preserve_first_n
        self._context: ContextWindow = ContextWindow(max_tokens=max_tokens, reserved_tokens=reserved_tokens)
        self._thought_history: List[Dict[str, Any]] = []
        self._task_memory: Dict[str, Any] = {}

    @property
    def messages(self) -> List[Dict[str, Any]]:
        return self._context.messages

    @property
    def current_tokens(self) -> int:
        return self._context.current_tokens

    @property
    def available_tokens(self) -> int:
        return self._context.available_tokens

    def set_task_context(
        self,
        task_id: str,
        title: str,
        description: Optional[str] = None,
        goals: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None
    ) -> None:
        """Initialize context for a specific task."""
        self._task_memory = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "goals": goals or [],
            "constraints": constraints or [],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "step_count": 0
        }

        # Add system prompt
        system_prompt = self._build_system_prompt()
        self._context.append("system", system_prompt)
        logger.info(f"Set task context for task {task_id}: {title}")

    def _build_system_prompt(self) -> str:
        """Build a system prompt from task memory."""
        base_prompt = "You are an autonomous AI agent executing a task. Behave as a helpful, reliable assistant."

        if self._task_memory:
            parts = [base_prompt]

            if self._task_memory.get("title"):
                parts.append(f"\nTask: {self._task_memory['title']}")

            if self._task_memory.get("description"):
                parts.append(f"\nDescription: {self._task_memory['description']}")

            if self._task_memory.get("goals"):
                parts.append("\nGoals:")
                for goal in self._task_memory["goals"]:
                    parts.append(f"  - {goal}")

            if self._task_memory.get("constraints"):
                parts.append("\nConstraints:")
                for constraint in self._task_memory["constraints"]:
                    parts.append(f"  - {constraint}")

            return "\n".join(parts)

        return base_prompt

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation context."""
        self._context.append(role, content)
        self._maybe_compact()

    def add_thought(self, content: str, is_reasoning: bool = True) -> None:
        """Add a thought/reasoning step to the history."""
        thought = {
            "type": "reasoning" if is_reasoning else "observation",
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._thought_history.append(thought)

        if is_reasoning and len(self._thought_history) > self.compaction_window:
            self._compact_thoughts()

    def _compact_thoughts(self) -> None:
        """Compact old thoughts into a summary."""
        if len(self._thought_history) <= self.compaction_window:
            return

        # Keep recent thoughts and summarize older ones
        recent = self._thought_history[-self.compaction_window:]
        older = self._thought_history[:-self.compaction_window]

        if older:
            summary = self._summarize_thoughts(older)
            logger.debug(f"Compacted {len(older)} thoughts into summary")
            self._thought_history = [summary] + recent

    def _summarize_thoughts(self, thoughts: List[Dict]) -> Dict[str, Any]:
        """Summarize a list of thoughts into a condensed form."""
        total_chars = sum(len(t.get("content", "")) for t in thoughts)

        return {
            "type": "summary",
            "content": f"[Compacted {len(thoughts)} thoughts, ~{total_chars} chars of reasoning]",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _maybe_compact(self) -> None:
        """Compact context if approaching token limit."""
        if self.current_tokens + self.reserved_tokens > self.max_tokens:
            self._compact_messages()

    def _compact_messages(self) -> None:
        """Remove oldest messages while preserving essential context."""
        if len(self._context.messages) <= self.preserve_first_n + 1:  # +1 for system
            return

        # Preserve system prompt and first N messages
        system_msg = self._context.messages[0] if self._context.messages else None
        preserved = self._context.messages[:self.preserve_first_n + 1]
        rest = self._context.messages[self.preserve_first_n + 1:]

        # Keep the task instructions and newest conversation that fits the budget.
        base = ([system_msg] if system_msg else []) + preserved[1:]
        recent = rest[-10:]
        budget = max(0, self.max_tokens - self.reserved_tokens)
        while recent and sum(self._context._estimate_tokens(message) for message in [*base, *recent]) > budget:
            recent.pop(0)
        removed_count = len(rest) - len(recent)

        self._context._messages = [*base, *recent]

        logger.debug(f"Compacted context, removed {removed_count} messages")

    def get_prompt(self, additional_instructions: Optional[str] = None) -> List[Dict[str, str]]:
        """Get the current prompt for the LLM."""
        prompt = self._context.to_list()

        if additional_instructions:
            prompt.append({"role": "system", "content": additional_instructions})

        return prompt

    def get_task_info(self) -> Optional[Dict[str, Any]]:
        """Get current task information."""
        return self._task_memory if self._task_memory else None

    def update_step_count(self, increment: int = 1) -> int:
        """Update the step count for the current task."""
        if self._task_memory:
            self._task_memory["step_count"] = self._task_memory.get("step_count", 0) + increment
            return self._task_memory["step_count"]
        return 0

    def reset(self) -> None:
        """Reset the context for a new task."""
        self._context = ContextWindow(max_tokens=self.max_tokens, reserved_tokens=self.reserved_tokens)
        self._thought_history = []
        self._task_memory = {}
        logger.debug("Context reset for new task")

    def snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the current context state."""
        return {
            "messages": [dict(m) for m in self._context.messages],
            "thought_history": list(self._thought_history),
            "task_memory": dict(self._task_memory),
            "current_tokens": self.current_tokens,
            "available_tokens": self.available_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Restore context from a snapshot."""
        self._context = ContextWindow(max_tokens=self.max_tokens, reserved_tokens=self.reserved_tokens)
        self._context._messages = snapshot.get("messages", [])
        self._thought_history = snapshot.get("thought_history", [])
        self._task_memory = snapshot.get("task_memory", {})
        logger.debug(f"Restored context snapshot from {snapshot.get('timestamp', 'unknown')}")


def count_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    return len(text) // 4 + 1


def truncate_to_tokens(messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
    """Truncate messages to fit within token limit."""
    result = []
    current_tokens = 0

    for msg in reversed(messages):
        msg_tokens = count_tokens(msg.get("content", ""))
        if current_tokens + msg_tokens > max_tokens and result:
            break
        result.insert(0, msg)
        current_tokens += msg_tokens

    return result
