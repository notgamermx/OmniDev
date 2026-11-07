#!/usr/bin/env python3
"""OmniDev CLI - Command line interface for the Personal AI Development Environment."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


class OmniDevCLI:
    """CLI for interacting with OmniDev local API."""

    def __init__(self, api_host: str = "localhost", api_port: int = 8000):
        self.api_url = f"http://{api_host}:{api_port}"
        self.client = httpx.Client(base_url=self.api_url, timeout=180.0)

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
        enabled: bool = True,
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
            "enabled": enabled,
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
        limit: int = 50,
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
        constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new task."""
        payload = {
            "agent_id": agent_id,
            "title": title,
            "description": description,
            "max_steps": max_steps,
            "goals": goals,
            "constraints": constraints,
        }
        response = self.client.post("/api/v1/tasks/", json=payload)
        response.raise_for_status()
        return response.json()

    def execute_task(
        self, task_id: int, project_root: str = ".", sync: bool = True
    ) -> Dict[str, Any]:
        """Execute a task."""
        if sync:
            response = self.client.post(
                f"/api/v1/tasks/{task_id}/execute", json={"project_root": project_root}
            )
        else:
            response = self.client.post(
                f"/api/v1/tasks/{task_id}/run", json={"project_root": project_root}
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

    def set_session_memory(
        self, key: str, value: Optional[str] = None, data: Optional[dict] = None
    ) -> Dict[str, Any]:
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
        response = self.client.get("/api/v1/file", params={"path": path})
        response.raise_for_status()
        return response.json()


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
        temperature=args.temperature,
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
    result = cli.list_tasks(
        agent_id=args.agent_id, status=args.status, limit=args.limit or 50
    )
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
        constraints=constraints,
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
    if args.subaction == "get":
        if not args.key:
            print("Error: --key required for get action")
            return 1
        result = cli.get_session_memory(args.key)
    elif args.subaction == "set":
        if not args.key:
            print("Error: --key required for set action")
            return 1
        result = cli.set_session_memory(
            args.key, args.value, args.data and json.loads(args.data)
        )
    else:
        print(f"Unknown action: {args.subaction}")
        return 1
    print(json.dumps(result, indent=2))
    return 0


def _desktop_connection():
    import os
    if os.name == "nt":
        try:
            return json.loads((Path(os.environ.get("OMNIDEV_HOME", Path.home() / ".omnidev")) / "desktop-connection.json").read_text())
        except (OSError, ValueError):
            pass
    return {}


def main():
    import os
    from urllib.parse import quote

    desktop = _desktop_connection()
    parser = argparse.ArgumentParser(
        prog="omnidev", description="OmniDev application and CLI"
    )
    parser.add_argument(
        "--url", default=os.environ.get("OMNIDEV_URL", desktop.get("url", "http://127.0.0.1:8000"))
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("OMNIDEV_TOKEN", ""),
        help="Prefer OMNIDEV_TOKEN to avoid shell history",
    )
    subs = parser.add_subparsers(dest="command", required=True)
    server = subs.add_parser(
        "serve", help="Initialize the database and serve the engine and web app"
    )
    server.add_argument("--host", default=None)
    server.add_argument("--port", type=int, default=None)
    subs.add_parser("health")
    subs.add_parser("providers")
    models = subs.add_parser("models", help="Browse models and manage the built-in router")
    models.add_argument("action", choices=["list", "pool", "save-pool", "setup"])
    models.add_argument("--provider", default="builtin")
    models.add_argument("--file", help="Private JSON file with routes or provider credentials")
    for name in ("agents", "tasks", "projects", "sessions"):
        sub = subs.add_parser(name)
        sub.add_argument(
            "action",
            choices=["list", "create", "get", "delete"]
            + (["run", "cancel"] if name == "tasks" else []),
        )
        sub.add_argument("id", nargs="?")
        sub.add_argument("--json", default="{}", help="JSON fields for creation")
        sub.add_argument("--path", default=".")
    connectors = subs.add_parser("connectors", help="Manage provider and command harness connections")
    connectors.add_argument("action", choices=["list", "save", "delete", "models", "install", "run"])
    connectors.add_argument("kind", nargs="?", choices=["providers", "harnesses"])
    connectors.add_argument("id", nargs="?")
    connectors.add_argument("--file", help="JSON connector definition; avoids keys in shell history")
    connectors.add_argument("--prompt")
    connectors.add_argument("--path", default=".")
    files = subs.add_parser("files")
    files.add_argument("path", nargs="?", default=".")
    read = subs.add_parser("read")
    read.add_argument("path")
    write = subs.add_parser("write")
    write.add_argument("path")
    write.add_argument("--from-file", required=True)
    run = subs.add_parser("terminal")
    run.add_argument("shell_command")
    run.add_argument("--path", default=".")
    memory = subs.add_parser("memory")
    memory.add_argument("action", choices=["list", "get", "set", "delete"])
    memory.add_argument("--key")
    memory.add_argument("--value")
    memory.add_argument("--session")
    memory.add_argument("--project", type=int)
    chat = subs.add_parser("chat")
    chat.add_argument("message", nargs="?")
    chat.add_argument("--provider", default="builtin")
    chat.add_argument("--model", default="auto")
    chat.add_argument("--session")
    chat.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    if not args.token and args.url == desktop.get("url"):
        args.token = desktop.get("token", "")
    if args.command == "serve":
        from alembic import command
        from alembic.config import Config
        from app.core.config import settings
        import uvicorn

        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).parent / "migrations")
        )
        command.upgrade(config, "head")
        host = args.host or settings.API_HOST
        if host not in {"127.0.0.1", "localhost", "::1"} and not (
            settings.API_TOKEN and len(settings.API_TOKEN.get_secret_value()) >= 32
        ):
            parser.error(
                "Remote binding requires API_TOKEN with at least 32 characters"
            )
        from app.main import app
        uvicorn.run(app, host=host, port=args.port or settings.API_PORT)
        return 0
    headers = {"Authorization": "Bearer " + args.token} if args.token else {}
    try:
        with httpx.Client(
            base_url=args.url.rstrip("/") + "/api/v1/",
            headers=headers,
            timeout=180,
            follow_redirects=True,
        ) as client:

            def req(path, method="GET", body=None):
                response = client.request(method, path, json=body)
                response.raise_for_status()
                return response.json()

            def show(value):
                print(json.dumps(value, indent=2))

            cmd = args.command
            if cmd == "health":
                show(req("health/"))
            elif cmd == "models":
                if args.action == "list":
                    show(req("models/catalog/" + quote(args.provider, safe="")))
                elif args.action == "pool":
                    show(req("models/pool"))
                else:
                    if not args.file:
                        parser.error("--file is required")
                    body = json.loads(Path(args.file).read_text(encoding="utf-8"))
                    path = "models/pool" if args.action == "save-pool" else "models/providers/" + quote(args.provider, safe="")
                    show(req(path, "PUT", body))
            elif cmd == "providers":
                show(req("chat/providers/"))
            elif cmd in {"agents", "tasks", "projects", "sessions"}:
                action = args.action
                if action not in {"list", "create"} and not args.id:
                    parser.error("This action requires an ID")
                suffix = "/" if cmd != "sessions" else ""
                path = (
                    cmd + suffix
                    if action in {"list", "create"}
                    else cmd + "/" + quote(args.id, safe="")
                )
                method = {
                    "list": "GET",
                    "get": "GET",
                    "create": "POST",
                    "delete": "DELETE",
                    "cancel": "DELETE",
                    "run": "POST",
                }[action]
                body = json.loads(args.json) if action == "create" else None
                if action == "run":
                    path += "/execute"
                    body = {"project_root": args.path}
                if cmd == "tasks" and action == "delete":
                    path = "tasks/"
                    body = int(args.id)
                show(req(path, method, body))
            elif cmd == "connectors":
                if args.action == "list":
                    show(req("connectors"))
                else:
                    if not args.kind or not args.id:
                        parser.error("Connector kind and ID are required")
                    path = f"connectors/{args.kind}/{quote(args.id, safe='')}"
                    if args.action == "save":
                        if not args.file:
                            parser.error("--file is required")
                        show(req(path, "PUT", json.loads(Path(args.file).read_text(encoding="utf-8"))))
                    elif args.action == "delete":
                        show(req(path, "DELETE"))
                    elif args.action == "models":
                        show(req(path + "/models"))
                    elif args.action == "install":
                        result = req(path + "/install", "POST")
                        show(result)
                        return result["exit_code"] or 0
                    else:
                        if not args.prompt:
                            parser.error("--prompt is required")
                        result = req(path + "/run", "POST", {"prompt": args.prompt, "path": args.path})
                        print(result["output"], end="")
                        return result["exit_code"] or 0
            elif cmd == "files":
                show(req("files?path=" + quote(args.path)))
            elif cmd == "read":
                print(req("file?path=" + quote(args.path))["content"], end="")
            elif cmd == "write":
                show(
                    req(
                        "file",
                        "PUT",
                        {
                            "path": args.path,
                            "content": Path(args.from_file).read_text(encoding="utf-8"),
                        },
                    )
                )
            elif cmd == "terminal":
                result = req(
                    "terminal",
                    "POST",
                    {"command": args.shell_command, "path": args.path},
                )
                print(result["output"], end="")
                return result["exit_code"] or 0
            elif cmd == "memory":
                path = (
                    f"memory/project/{args.project}"
                    if args.project is not None
                    else "memory/session"
                )
                if args.action in {"get", "set", "delete"} and not args.key:
                    parser.error("--key is required")
                body = {"key": args.key, "value": args.value}
                if args.action in {"get", "delete"}:
                    path += "/" + quote(args.key, safe="")
                if args.session:
                    body["session_id"] = args.session
                    if args.action != "set":
                        path += "?session_id=" + quote(args.session)
                show(
                    req(
                        path,
                        {
                            "list": "GET",
                            "get": "GET",
                            "set": "POST",
                            "delete": "DELETE",
                        }[args.action],
                        body if args.action == "set" else None,
                    )
                )
            elif cmd == "chat":
                if not args.message and not args.interactive:
                    parser.error("Provide a message or --interactive")
                session = (
                    req("sessions/" + args.session)
                    if args.session
                    else req(
                        "sessions",
                        "POST",
                        {"name": (args.message or "CLI conversation")[:70]},
                    )
                )
                print("Session: " + session["id"], file=sys.stderr)
                messages = session["messages"]

                def send(message):
                    messages.append({"role": "user", "content": message})
                    req("sessions/" + session["id"], "PUT", {"messages": messages})
                    text = ""
                    try:
                        with client.stream(
                            "POST",
                            "chat/completions/stream",
                            json={
                                "provider": args.provider,
                                "model": args.model,
                                "messages": messages,
                            },
                        ) as response:
                            response.raise_for_status()
                            for line in response.iter_lines():
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    break
                                chunk = json.loads(data)
                                if "error" in chunk:
                                    raise ValueError(chunk["error"]["detail"])
                                content = (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                text += content
                                print(content, end="", flush=True)
                        print()
                    finally:
                        messages.append({"role": "assistant", "content": text})
                        req("sessions/" + session["id"], "PUT", {"messages": messages})

                if args.message:
                    send(args.message)
                if args.interactive:
                    while True:
                        try:
                            message = input("omnidev> ")
                        except EOFError:
                            break
                        if message.strip() in {"/exit", "/quit"}:
                            break
                        if message.strip():
                            send(message)
        return 0
    except httpx.HTTPStatusError as exc:
        print(f"Error: {exc.response.status_code} {exc.response.text}", file=sys.stderr)
        return 1
    except (httpx.HTTPError, ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
