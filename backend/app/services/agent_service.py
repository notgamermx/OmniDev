"""Agent service for managing AI agents."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.agent import Agent
from app.services.llm_providers import PROVIDER_BY_ID
from app.services.tool_registry import BuiltInToolRegistry, get_builtin_tool_registry, Permission

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing AI agents."""

    def __init__(self, tool_registry: Optional[BuiltInToolRegistry] = None) -> None:
        self.tool_registry = tool_registry or get_builtin_tool_registry()

    def _with_db(self, operation):
        """Execute an operation with a database session."""
        db = SessionLocal()
        try:
            return operation(db)
        finally:
            db.close()

    async def create_agent(
        self,
        name: str,
        description: Optional[str] = None,
        provider: str = "ollama",
        model: str = "llama3.1:8b",
        system_prompt: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        max_steps: int = 25,
        temperature: float = 0.0,
        enabled: bool = True
    ) -> Agent:
        """Create a new agent definition."""
        if provider not in PROVIDER_BY_ID:
            raise ValueError(f"Provider '{provider}' is not registered")

        # Validate tools if provided
        if tool_names:
            for tool_name in tool_names:
                if not self.tool_registry.get_tool(tool_name):
                    raise ValueError(f"Tool '{tool_name}' not found")
                if not self.tool_registry.is_enabled(tool_name):
                    raise ValueError(f"Tool '{tool_name}' is disabled")

        # Default system prompt if none provided
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        # Default tools to all enabled tools
        if tool_names is None:
            tool_names = [t.name for t in self.tool_registry.list_tools() if self.tool_registry.is_enabled(t.name)]

        def op(db):
            agent = Agent(
                name=name,
                description=description,
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                tool_names=tool_names,
                max_steps=max_steps,
                temperature=temperature,
                enabled=enabled,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            db.add(agent)
            db.commit()
            db.refresh(agent)
            logger.info(f"Created agent {agent.id}: {name}")
            return agent

        return self._with_db(op)

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for new agents."""
        return """You are an autonomous AI agent designed to execute tasks.

You should:
1. Think through problems step by step
2. Use available tools to gather information and take actions
3. Be thorough and careful in your reasoning
4. Report your findings clearly

Available tools can be invoked using the ACTION format:
ACTION: tool_name{"arg": "value"}

Use THOUGHT for reasoning:
THOUGHT: [your analysis here]

To complete a task, say:
COMPLETE: [final summary]

Work within the project boundaries and respect all constraints.
"""

    async def get_agent(self, agent_id: int) -> Optional[Agent]:
        """Get an agent by ID."""
        def op(db):
            return db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        return self._with_db(op)

    async def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        def op(db):
            return db.execute(select(Agent).where(Agent.name == name)).scalar_one_or_none()
        return self._with_db(op)

    async def list_agents(self, enabled_only: bool = True) -> List[Agent]:
        """List all agents, optionally only enabled ones."""
        def op(db):
            query = select(Agent)
            if enabled_only:
                query = query.where(Agent.enabled == True)
            return db.execute(query.order_by(Agent.name)).scalars().all()
        return self._with_db(op)

    async def list_agent_tools(self, agent_id: int) -> List[Dict[str, Any]]:
        """List tools available to an agent."""
        def op(db):
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            available_tools = []
            for tool_name in agent.tool_names:
                tool_def = self.tool_registry.get_tool(tool_name)
                if tool_def:
                    available_tools.append({
                        "name": tool_def.name,
                        "description": tool_def.description,
                        "permission": tool_def.permission.value,
                        "enabled": self.tool_registry.is_enabled(tool_def.name)
                    })
            return available_tools
        return self._with_db(op)

    async def assign_tool(self, agent_id: int, tool_name: str) -> bool:
        """Assign a tool to an agent."""
        # Verify tool exists
        tool_def = self.tool_registry.get_tool(tool_name)
        if not tool_def:
            raise ValueError(f"Tool '{tool_name}' not found")

        def op(db):
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                return False

            if tool_name not in agent.tool_names:
                agent.tool_names.append(tool_name)
                agent.updated_at = datetime.now(timezone.utc).isoformat()
                db.commit()
                logger.info(f"Assigned tool '{tool_name}' to agent {agent_id}")
            return True
        return self._with_db(op)

    async def remove_tool(self, agent_id: int, tool_name: str) -> bool:
        """Remove a tool from an agent."""
        def op(db):
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                return False

            if tool_name in agent.tool_names:
                agent.tool_names.remove(tool_name)
                agent.updated_at = datetime.now(timezone.utc).isoformat()
                db.commit()
                logger.info(f"Removed tool '{tool_name}' from agent {agent_id}")
            return True
        return self._with_db(op)

    async def update_agent(
        self,
        agent_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_steps: Optional[int] = None,
        temperature: Optional[float] = None,
        enabled: Optional[bool] = None
    ) -> Optional[Agent]:
        """Update agent properties."""
        def op(db):
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                return None

            if name is not None:
                agent.name = name
            if description is not None:
                agent.description = description
            if model is not None:
                agent.model = model
            if system_prompt is not None:
                agent.system_prompt = system_prompt
            if max_steps is not None:
                agent.max_steps = max_steps
            if temperature is not None:
                agent.temperature = temperature
            if enabled is not None:
                agent.enabled = enabled

            agent.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            db.refresh(agent)
            return agent
        return self._with_db(op)

    async def delete_agent(self, agent_id: int) -> bool:
        """Delete an agent."""
        def op(db):
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                return False

            db.delete(agent)
            db.commit()
            logger.info(f"Deleted agent {agent_id}")
            return True
        return self._with_db(op)

    def get_agent_config(self, agent_id: int) -> Dict[str, Any]:
        """Get agent configuration for use with providers."""
        agent = self._with_db(
            lambda db: db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        )
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        return {
            "provider_id": agent.provider,
            "model": agent.model,
            "temperature": agent.temperature,
            "max_steps": agent.max_steps,
            "tool_names": list(agent.tool_names or []),
        }


# Global agent service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get the global agent service instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
