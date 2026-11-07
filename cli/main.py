#!/usr/bin/env python3
"""OmniDev CLI - Command line interface for the Personal AI Development Environment."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


class OmniDevCLI:
    """CLI for interacting with OmniDev local API."""

    def __init__(self, api_host: str = "localhost", api_port: int = 8000):
        self.api_url = f"http://{api_host}:{api_port}"
        self.client = httpx.Client(base_url=self.api_url, timeout=30.0)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    # ==========================================
    # Health & Status
    # ==========================================

    def health(self) -> Dict[str, Any]:
        """Check API health status."""
        response = self.client.get("/api/v1/health/")
        response.raise_for_status()
        return response.json()

    def system(self) -> Dict[str, Any]:
        """Get system information."""
        response = self.client.get("/api/v1/system/")
        response.raise_for_status()
        return response.json()

    # ==========================================
    # Agent Management
    # ==========================================

    def list_agents(self, enabled_only: bool = True) -> Dict[str, Any]:
        """List all configured agents."""
        params = {"enabled_only": str(enabled_only).lower()}
        response = self.client.get("/api/v1/agents/", params=params)
        response.raise_for_status()
        return response.json()

    def create_agent(
        self,
        name: str,
        model: str,
        provider: str = "ollama",
        system_prompt: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        max_steps: int = 25,
        temperature: float = 0.0,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """Create a new agent."""
        payload = {
            "name": name,
            "model": model,
            "provider": provider,
            "system_prompt": system_prompt,
            "tool_names": tool_names,
            "max_steps": max_steps,
            "temperature": temperature,
            "enabled": enabled
        }
        response = self.client.post("/api/v1/agents/", json=payload)
        response.raise_for_status()
        return response.json()

    def get_agent(self, agent_id: int) -> Dict[str, Any]:
        """Get an agent by ID."""
        response = self.client.get(f"/api/v1/agents/{agent_id}")
        response.raise_for_status()
        return response.json()

    def delete_agent(self, agent_id: int) -> Dict[str, Any]:
        """Delete an agent."""
        response = self.client.delete(f"/api/v1/agents/{agent_id}")
        response.raise_for_status()
        return response.json()

    # ==========================================
    # Task Management
    # ==========================================

    def list_tasks(
        self,
        agent_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List tasks with optional filtering."""
        params = {"limit": limit}
        if agent_id is not None:
            params["agent_id"] = agent_id
        if status is not None:
            params["status"] = status

        response = self.client.get("/api/v1/tasks/", params=params)
        response.raise_for_status()
        return response.json()

    def create_task(
        self,
        agent_id: int,
        title: str,
        description: Optional[str] = None,
        max_steps: int = 25,
        goals: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new task."""
        payload = {
            "agent_id": agent_id,
            "title": title,
            "description": description,
            "max_steps": max_steps,
            "goals": goals,
            "constraints": constraints
        }
        response = self.client.post("/api/v1/tasks/", json=payload)
        response.raise_for_status()
        return response.json()

    def execute_task(self, task_id: int, project_root: str = ".", sync: bool = True) -> Dict[str, Any]:
        """Execute a task."""
        if sync:
            response = self.client.post(
                f"/api/v1/tasks/{task_id}/execute",
                json={"project_root": project_root}
            )
        else:
            response = self.client.post(
                f"/api/v1/tasks/{task_id}/execute/sync",
                json={"project_root": project_root}
            )
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get a task with full execution history."""
        response = self.client.get(f"/api/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """Cancel a running task."""
        response = self.client.delete(f"/api/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    # ==========================================
    # Memory Management (Phase 5)
    # ==========================================

    def get_session_memory(self, key: str) -> Dict[str, Any]:
        """Get session memory."""
        response = self.client.get(f"/api/v1/memory/session/{key}")
        response.raise_for_status()
        return response.json()

    def set_session_memory(self, key: str, value: Optional[str] = None, data: Optional[dict] = None) -> Dict[str, Any]:
        """Set session memory."""
        payload = {"key": key}
        if value is not None:
            payload["value"] = value
        if data is not None:
            payload["data"] = data
        response = self.client.post("/api/v1/memory/session", json=payload)
        response.raise_for_status()
        return response.json()

    def list_project_memories(self, project_id: int) -> Dict[str, Any]:
        """List project memories."""
        response = self.client.get(f"/api/v1/memory/project/{project_id}")
        response.raise_for_status()
        return response.json()

    # ==========================================
    # Tools Execution
    # ==========================================

    def read_file(self, path: str, project_root: str = ".") -> Dict[str, Any]:
        """Read a file using a tool call."""
        # This would need to go through a task execution
        # For now, this is a placeholder for direct tool access
        payload = {
            "agent_id": 1,  # Default agent
            "title": f"Read file: {path}",
            "description": f"Reading file at {path}",
            "max_steps": 10
        }
        task = self.create_task(1, payload["title"], payload["description"])
        return self.execute_task(task["id"], project_root)


def cmd_health(cli: OmniDevCLI, args) -> int:
    """Check health."""
    result = cli.health()
    print(json.dumps(result, indent=2))
    return 0


def cmd_system(cli: OmniDevCLI, args) -> int:
    """Show system info."""
    result = cli.system()
    print(json.dumps(result, indent=2))
    return 0


def cmd_list_agents(cli: OmniDevCLI, args) -> int:
    """List agents."""
    result = cli.list_agents()
    print(json.dumps(result, indent=2))
    return 0


def cmd_create_agent(cli: OmniDevCLI, args) -> int:
    """Create an agent."""
    result = cli.create_agent(
        name=args.name,
        model=args.model,
        provider=args.provider or "ollama",
        system_prompt=args.system_prompt,
        tool_names=args.tools.split(",") if args.tools else None,
        max_steps=args.max_steps,
        temperature=args.temperature
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_delete_agent(cli: OmniDevCLI, args) -> int:
    """Delete an agent."""
    result = cli.delete_agent(args.agent_id)
    print(json.dumps(result, indent=2))
    return 0


def cmd_list_tasks(cli: OmniDevCLI, args) -> int:
    """List tasks."""
    result = cli.list_tasks(agent_id=args.agent_id, status=args.status, limit=args.limit or 50)
    print(json.dumps(result, indent=2))
    return 0


def cmd_create_task(cli: OmniDevCLI, args) -> int:
    """Create a task."""
    goals = args.goals.split(",") if args.goals else None
    constraints = args.constraints.split(",") if args.constraints else None

    result = cli.create_task(
        agent_id=args.agent_id,
        title=args.title,
        description=args.description,
        max_steps=args.max_steps,
        goals=goals,
        constraints=constraints
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_execute_task(cli: OmniDevCLI, args) -> int:
    """Execute a task."""
    result = cli.execute_task(args.task_id, args.project_root or ".")
    print(json.dumps(result, indent=2))
    return 0


def cmd_get_task(cli: OmniDevCLI, args) -> int:
    """Get a task."""
    result = cli.get_task(args.task_id)
    print(json.dumps(result, indent=2))
    return 0


def cmd_memory_session(cli: OmniDevCLI, args) -> int:
    """Session memory operations."""
    if args.action == "get":
        result = cli.get_session_memory(args.key)
    elif args.action == "set":
        if not args.key:
            print("Error: --key required for set action")
            return 1
        result = cli.set_session_memory(args.key, args.value, args.data and json.loads(args.data))
    else:
        print(f"Unknown action: {args.action}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="omnidev",
        description="OmniDev - Personal AI Development Environment CLI"
    )

    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Health command
    health_parser = subparsers.add_parser("health", help="Check API health")
    health_parser.set_defaults(func=lambda cli, args: cmd_health(cli, args))

    # System command
    system_parser = subparsers.add_parser("system", help="Show system info")
    system_parser.set_defaults(func=lambda cli, args: cmd_system(cli, args))

    # Agent commands
    agents_parser = subparsers.add_parser("agents", help="Agent management")
    agents_parser.add_argument("action", choices=["list", "create", "delete"])
    agents_parser.add_argument("--name", help="Agent name (for create)")
    agents_parser.add_argument("--model", help="Model name (for create)")
    agents_parser.add_argument("--provider", help="Provider (for create)")
    agents_parser.add_argument("--system-prompt", help="System prompt")
    agents_parser.add_argument("--tools", help="Comma-separated tool names")
    agents_parser.add_argument("--max-steps", type=int, default=25)
    agents_parser.add_argument("--temperature", type=float, default=0.0)
    agents_parser.add_argument("--agent-id", type=int, help="Agent ID (for delete)")
    agents_parser.set_defaults(func=lambda cli, args: (
        cmd_agents_list(cli, args) if args.action == "list"
        else cmd_create_agent(cli, args) if args.action == "create"
        else cmd_delete_agent(cli, args)
    ))

    # Task commands
    tasks_parser = subparsers.add_parser("tasks", help="Task management")
    tasks_parser.add_argument("action", choices=["list", "create", "execute", "get"])
    tasks_parser.add_argument("--agent-id", type=int, help="Agent ID")
    tasks_parser.add_argument("--status", help="Filter by status")
    tasks_parser.add_argument("--title", help="Task title")
    tasks_parser.add_argument("--description", help="Task description")
    tasks_parser.add_argument("--task-id", type=int, help="Task ID")
    tasks_parser.add_argument("--max-steps", type=int, default=25)
    tasks_parser.add_argument("--goals", help="Comma-separated goals")
    tasks_parser.add_argument("--constraints", help="Comma-separated constraints")
    tasks_parser.add_argument("--project-root", help="Project root directory")
    tasks_parser.set_defaults(func=lambda cli, args: (
        cmd_list_tasks(cli, args) if args.action == "list"
        else cmd_create_task(cli, args) if args.action == "create"
        else cmd_execute_task(cli, args) if args.action == "execute"
        else cmd_get_task(cli, args)
    ))

    # Memory commands
    memory_parser = subparsers.add_parser("memory", help="Memory operations")
    memory_parser.add_argument("action", choices=["session"])
    memory_parser.add_argument("subaction", choices=["get", "set"])
    memory_parser.add_argument("--key", help="Memory key")
    memory_parser.add_argument("--value", help="Memory value")
    memory_parser.add_argument("--data", help="JSON data")
    memory_parser.set_defaults(func=lambda cli, args: cmd_memory_session(cli, args))

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    cli = OmniDevCLI(args.host, args.port)
    try:
        return args.func(cli, args)
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        cli.close()


def cmd_agents_list(cli: OmniDevCLI, args):
    """List agents helper."""
    result = cli.list_agents()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())