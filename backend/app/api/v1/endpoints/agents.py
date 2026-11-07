"""Agent API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, BackgroundTasks

from app.services.agent_service import (
    AgentService,
    get_agent_service as _get_agent_service,
)
from app.services.llm_providers import PROVIDER_BY_ID

router = APIRouter(tags=["Agents"])


# Default dependency
def get_agent_service() -> AgentService:
    return _get_agent_service()


@router.get("/", response_model=dict, summary="List all agents")
async def list_agents(enabled_only: bool = True):
    """List all configured agents."""
    service = get_agent_service()
    agents = await service.list_agents(enabled_only=enabled_only)
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "provider": a.provider,
                "model": a.model,
                "temperature": a.temperature,
                "max_steps": a.max_steps,
                "enabled": a.enabled,
                "tool_count": len(a.tool_names),
                "created_at": a.created_at,
                "updated_at": a.updated_at,
            }
            for a in agents
        ]
    }


@router.post("/", response_model=dict, summary="Create a new agent")
async def create_agent(
    name: str = Body(..., description="Unique agent name"),
    description: Optional[str] = Body(None, description="Agent description"),
    provider: str = Body("ollama", description="LLM provider ID"),
    model: str = Body(..., description="Model name"),
    system_prompt: Optional[str] = Body(None, description="Custom system prompt"),
    tool_names: Optional[List[str]] = Body(
        None, description="List of tool names to enable"
    ),
    max_steps: int = Body(25, ge=1, le=200, description="Maximum execution steps"),
    temperature: float = Body(0.0, ge=0, le=2, description="LLM temperature"),
    enabled: bool = Body(True, description="Whether agent is enabled"),
):
    """Create a new AI agent definition."""
    # Validate provider
    if provider not in PROVIDER_BY_ID:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")

    # Validate tools if provided
    if tool_names:
        from app.services.tool_registry import get_builtin_tool_registry

        registry = get_builtin_tool_registry()
        for tool_name in tool_names:
            if not registry.get_tool(tool_name):
                raise HTTPException(
                    status_code=404, detail=f"Tool '{tool_name}' not found"
                )
            if not registry.is_enabled(tool_name):
                raise HTTPException(
                    status_code=400, detail=f"Tool '{tool_name}' is disabled"
                )

    service = get_agent_service()

    try:
        agent = await service.create_agent(
            name=name,
            description=description,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            tool_names=tool_names,
            max_steps=max_steps,
            temperature=temperature,
            enabled=enabled,
        )
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "provider": agent.provider,
            "model": agent.model,
            "temperature": agent.temperature,
            "max_steps": agent.max_steps,
            "enabled": agent.enabled,
            "tool_names": agent.tool_names,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{agent_id}", response_model=dict, summary="Get an agent by ID")
async def get_agent(agent_id: int = Path(..., description="Agent ID")):
    """Get an agent definition by ID."""
    service = get_agent_service()
    agent = await service.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Get available tools
    tools = await service.list_agent_tools(agent_id)

    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model": agent.model,
        "system_prompt": agent.system_prompt,
        "temperature": agent.temperature,
        "max_steps": agent.max_steps,
        "enabled": agent.enabled,
        "tools": tools,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


@router.get("/{agent_id}/tools", response_model=dict, summary="List tools for an agent")
async def list_agent_tools(agent_id: int = Path(..., description="Agent ID")):
    """List all tools available to an agent."""
    service = get_agent_service()
    tools = await service.list_agent_tools(agent_id)

    return {"agent_id": agent_id, "tools": tools, "count": len(tools)}


@router.put("/{agent_id}", response_model=dict, summary="Update an agent")
async def update_agent(
    agent_id: int = Path(..., description="Agent ID"),
    name: Optional[str] = Body(None, description="New agent name"),
    description: Optional[str] = Body(None, description="New description"),
    model: Optional[str] = Body(None, description="New model name"),
    system_prompt: Optional[str] = Body(None, description="New system prompt"),
    max_steps: Optional[int] = Body(None, description="New max steps"),
    temperature: Optional[float] = Body(None, description="New temperature"),
    enabled: Optional[bool] = Body(None, description="Enable/disable agent"),
):
    """Update an agent's configuration."""
    service = get_agent_service()
    agent = await service.update_agent(
        agent_id=agent_id,
        name=name,
        description=description,
        model=model,
        system_prompt=system_prompt,
        max_steps=max_steps,
        temperature=temperature,
        enabled=enabled,
    )

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model": agent.model,
        "enabled": agent.enabled,
        "updated_at": agent.updated_at,
    }


@router.post(
    "/{agent_id}/tools/{tool_name}",
    response_model=dict,
    summary="Assign a tool to an agent",
)
async def assign_tool(
    agent_id: int = Path(..., description="Agent ID"),
    tool_name: str = Path(..., description="Tool name"),
):
    """Assign a tool to an agent."""
    service = get_agent_service()
    success = await service.assign_tool(agent_id, tool_name)

    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    agent = await service.get_agent(agent_id)
    return {
        "agent_id": agent_id,
        "tool_name": tool_name,
        "success": True,
        "tools": agent.tool_names,
    }


@router.delete(
    "/{agent_id}/tools/{tool_name}",
    response_model=dict,
    summary="Remove a tool from an agent",
)
async def remove_tool(
    agent_id: int = Path(..., description="Agent ID"),
    tool_name: str = Path(..., description="Tool name"),
):
    """Remove a tool from an agent."""
    service = get_agent_service()
    success = await service.remove_tool(agent_id, tool_name)

    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    agent = await service.get_agent(agent_id)
    return {
        "agent_id": agent_id,
        "tool_name": tool_name,
        "success": True,
        "tools": agent.tool_names,
    }


@router.delete("/{agent_id}", response_model=dict, summary="Delete an agent")
async def delete_agent(agent_id: int = Path(..., description="Agent ID")):
    """Delete an agent and all its tasks."""
    service = get_agent_service()
    success = await service.delete_agent(agent_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return {"deleted": True, "agent_id": agent_id}
