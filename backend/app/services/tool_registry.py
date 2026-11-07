"""Tool registry with built-in file/shell/web tools and permission levels."""

import asyncio
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
from urllib.parse import urlparse

from app.core.config import settings
from app.core.security import resolve_within_root
from app.services.llm_providers import OpenAICompatibleProvider, make_provider

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Permission levels for tool execution."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class ToolDefinition:
    """Definition of a tool that can be invoked by agents."""
    name: str
    description: str
    permission: Permission = Permission.READ
    enabled: bool = True
    input_schema: dict = None
    output_schema: dict = None

    def __post_init__(self):
        if self.input_schema is None:
            self.input_schema = {"type": "object", "properties": {}, "required": []}
        if self.output_schema is None:
            self.output_schema = {"type": "object"}


class ToolHandler(ABC):
    """Abstract base class for tool handlers."""

    @abstractmethod
    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with given arguments."""
        pass

    def validate_args(self, args: dict[str, Any]) -> tuple[bool, str]:
        """Validate arguments against input schema. Returns (valid, error_message)."""
        return True, ""


class BuiltInToolRegistry:
    """Registry of built-in tools available to all agents."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, ToolHandler] = {}
        self._permission_levels: Dict[str, Permission] = {}
        self._initialize_builtins()

    def _initialize_builtins(self) -> None:
        """Register all built-in tools."""
        # File tools
        self.register_tool(
            ToolDefinition(
                name="read_file",
                description="Read the contents of a file within the project. Returns file contents as text.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file to read"}
                    },
                    "required": ["path"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "size": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["read_file"] = ReadFileHandler()

        self.register_tool(
            ToolDefinition(
                name="write_file",
                description="Write content to a file within the project. Creates or overwrites the file.",
                permission=Permission.WRITE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to write to"},
                        "content": {"type": "string", "description": "Content to write to the file"}
                    },
                    "required": ["path", "content"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "written": {"type": "boolean"},
                        "size": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["write_file"] = WriteFileHandler()

        self.register_tool(
            ToolDefinition(
                name="list_files",
                description="List files in a directory within the project.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to list", "default": "."}
                    },
                    "required": []
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "files": {"type": "array", "items": {"type": "string"}},
                        "count": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["list_files"] = ListFilesHandler()

        self.register_tool(
            ToolDefinition(
                name="shell",
                description="Execute a shell command. Warning: powerful command execution capability.",
                permission=Permission.EXECUTE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                    },
                    "required": ["command"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["shell"] = ShellHandler()

        self.register_tool(
            ToolDefinition(
                name="web_search",
                description="Search the web for information. Requires internet connectivity.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Maximum results to return", "default": 5}
                    },
                    "required": ["query"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "count": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["web_search"] = WebSearchHandler()

        # Planning/analysis tools
        self.register_tool(
            ToolDefinition(
                name="think",
                description="Internal reasoning tool. Use to think through problems step by step without taking external actions.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "thought": {"type": "string", "description": "The reasoning or analysis to process"},
                        "context": {"type": "string", "description": "Optional context for the thought", "default": ""}
                    },
                    "required": ["thought"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "reflection": {"type": "string"}
                    }
                }
            )
        )
        self._handlers["think"] = ThinkHandler()

        # Git tools
        self.register_tool(
            ToolDefinition(
                name="git_status",
                description="Get git status of the repository. Shows modified, staged, and untracked files.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the git repository", "default": "."}
                    },
                    "required": []
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "clean": {"type": "boolean"},
                        "modified": {"type": "array", "items": {"type": "string"}},
                        "staged": {"type": "array", "items": {"type": "string"}},
                        "untracked": {"type": "array", "items": {"type": "string"}},
                        "branches": {"type": "array", "items": {"type": "string"}},
                        "current_branch": {"type": "string"}
                    }
                }
            )
        )
        self._handlers["git_status"] = GitStatusHandler()

        self.register_tool(
            ToolDefinition(
                name="git_commit",
                description="Create a git commit with the specified message.",
                permission=Permission.WRITE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Commit message"},
                        "all": {"type": "boolean", "description": "Stage all changes", "default": True},
                        "path": {"type": "string", "description": "Path to the git repository", "default": "."}
                    },
                    "required": ["message"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "hash": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            )
        )
        self._handlers["git_commit"] = GitCommitHandler()

        self.register_tool(
            ToolDefinition(
                name="git_diff",
                description="Show git diff of changes in the working directory or staged changes.",
                permission=Permission.READ,
                input_schema={
                    "type": "object",
                    "properties": {
                        "staged": {"type": "boolean", "description": "Show staged changes instead of working directory", "default": False},
                        "path": {"type": "string", "description": "Path to the git repository", "default": "."}
                    },
                    "required": []
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "diff": {"type": "string"},
                        "files_changed": {"type": "integer"}
                    }
                }
            )
        )
        self._handlers["git_diff"] = GitDiffHandler()

    def register_tool(self, definition: ToolDefinition) -> None:
        """Register a new tool."""
        self._tools[definition.name] = definition
        logger.info(f"Registered tool: {definition.name}")

    def register_handler(self, name: str, handler: ToolHandler) -> None:
        """Register a handler for a tool."""
        self._handlers[name] = handler
        logger.debug(f"Registered handler for: {name}")

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool. Returns True if it existed."""
        if name in self._tools:
            del self._tools[name]
            if name in self._handlers:
                del self._handlers[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        """Get a tool handler by name."""
        return self._handlers.get(name)

    def list_tools(self, permission_filter: Optional[Permission] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by permission level."""
        tools = list(self._tools.values())
        if permission_filter:
            tools = [t for t in tools if t.permission == permission_filter]
        return tools

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is enabled."""
        tool = self._tools.get(name)
        if tool is None or not tool.enabled:
            return False
        return name != "shell" or settings.TERMINAL_ENABLED

    def validate_args(self, name: str, args: Any) -> tuple[bool, str]:
        """Validate model supplied arguments against the registered JSON schema."""
        tool = self._tools.get(name)
        if tool is None:
            return False, f"Tool '{name}' not found"
        if not isinstance(args, dict):
            return False, "Tool arguments must be a JSON object"

        schema = tool.input_schema or {}
        properties = schema.get("properties", {})
        missing = set(schema.get("required", ())) - args.keys()
        if missing:
            return False, f"Missing required tool arguments: {', '.join(sorted(missing))}"
        unknown = args.keys() - properties.keys()
        if unknown:
            return False, f"Unknown tool arguments: {', '.join(sorted(unknown))}"

        validators = {
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": lambda value: isinstance(value, bool),
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
        }
        for key, value in args.items():
            expected = properties[key].get("type")
            if expected in validators and not validators[expected](value):
                return False, f"Tool argument '{key}' must be {expected}"
        return True, ""

    def has_permission(self, tool_name: str, required_permission: Permission) -> bool:
        """Check if a tool has the required permission level."""
        tool = self._tools.get(tool_name)
        if not tool:
            return False
        return self._has_permission(tool.permission, required_permission)

    def _has_permission(self, tool_permission: Permission, required_permission: Permission) -> bool:
        """Check if tool_permission is at or above required_permission."""
        permission_hierarchy = {
            Permission.READ: 1,
            Permission.WRITE: 2,
            Permission.EXECUTE: 3,
            Permission.ADMIN: 4,
        }
        return permission_hierarchy.get(tool_permission, 0) >= permission_hierarchy.get(required_permission, 0)


# Global singleton
_builtin_registry: Optional[BuiltInToolRegistry] = None


def get_builtin_tool_registry() -> BuiltInToolRegistry:
    """Get the singleton built-in tool registry."""
    global _builtin_registry
    if _builtin_registry is None:
        _builtin_registry = BuiltInToolRegistry()
    return _builtin_registry


# Tool Handlers

class ReadFileHandler(ToolHandler):
    """Handler for reading files."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        path_str = args.get("path", ".")
        project_root = context.get("project_root", Path.cwd())

        try:
            full_path = resolve_within_root(project_root, path_str)
            content = full_path.read_text()
            return {
                "content": content,
                "size": len(content),
                "path": str(full_path)
            }
        except Exception as e:
            logger.error(f"Failed to read file {path_str}: {e}")
            raise RuntimeError(f"Failed to read file: {e}")


class WriteFileHandler(ToolHandler):
    """Handler for writing files."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        path_str = args.get("path", "")
        content = args.get("content", "")
        project_root = context.get("project_root", Path.cwd())

        try:
            full_path = resolve_within_root(project_root, path_str)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return {
                "written": True,
                "size": len(content),
                "path": str(full_path)
            }
        except Exception as e:
            logger.error(f"Failed to write file {path_str}: {e}")
            raise RuntimeError(f"Failed to write file: {e}")


class ListFilesHandler(ToolHandler):
    """Handler for listing directory contents."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        path_str = args.get("path", ".")
        project_root = context.get("project_root", Path.cwd())

        try:
            full_path = resolve_within_root(project_root, path_str)
            items = []
            for item in full_path.iterdir():
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0
                })
            return {
                "files": items,
                "count": len(items),
                "path": str(full_path)
            }
        except Exception as e:
            logger.error(f"Failed to list files {path_str}: {e}")
            raise RuntimeError(f"Failed to list files: {e}")


class ShellHandler(ToolHandler):
    """Handler for executing shell commands."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        command = args.get("command", "")
        timeout = args.get("timeout", 30)

        # Security: Check for dangerous patterns
        dangerous_patterns = ["rm -rf", "mkfs", "dd if=", "chmod 777", "chown -R"]
        for pattern in dangerous_patterns:
            if pattern in command:
                raise RuntimeError(f"Potentially dangerous command blocked: {pattern}")

        from app.services.process_service import run_command
        result = await run_command(command, context.get("project_root", Path.cwd()), min(120, max(1, timeout)))
        return {**result, "stdout": result["output"], "stderr": "", "command": command}


class WebSearchHandler(ToolHandler):
    """Handler for web search using LLM providers."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "")
        max_results = args.get("max_results", 5)
        provider_id = context.get("provider", "ollama")
        model = context.get("model", "llama3.1:8b")

        try:
            provider = make_provider(provider_id)
            search_prompt = f"""
Search for information about: {query}

Return at most {max_results} relevant results with:
- A brief title/description
- A URL/source
- The key information

Format as JSON array of objects with "title", "url", "info" fields.
            """

            response = await provider.chat_completion(
                model=model,
                messages=[{"role": "user", "content": search_prompt}],
                temperature=0.0,
                max_tokens=1000
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            try:
                results = json.loads(content)
            except json.JSONDecodeError:
                results = [{"title": "Search Results", "url": "", "info": content}]

            await provider.close()

            return {
                "query": query,
                "results": results[:max_results],
                "count": min(len(results), max_results)
            }
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            raise RuntimeError(f"Web search failed: {e}")


class ThinkHandler(ToolHandler):
    """Handler for internal reasoning."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        thought = args.get("thought", "")
        previous_thoughts = context.get("thoughts", [])

        reflection = f"""
Previous thoughts: {len(previous_thoughts)} thoughts recorded.
Current thought process:
{thought}

Summary: Continue reasoning with this analysis in mind.
        """

        return {
            "reflection": reflection,
            "thought_count": len(previous_thoughts)
        }


class GitStatusHandler(ToolHandler):
    """Handler for git status command."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        import subprocess
        path = args.get("path", ".")
        project_root = resolve_within_root(Path(context.get("project_root", Path.cwd())), path)

        try:
            # First check if we're in a git repo
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "rev-parse", "--git-dir",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            if result.returncode != 0:
                return {
                    "clean": True,
                    "modified": [],
                    "staged": [],
                    "untracked": [],
                    "branches": [],
                    "current_branch": None,
                    "not_a_git_repo": True
                }

            # Get current branch
            branch_result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "branch", "--show-current",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            branch_stdout, _ = await branch_result.communicate()
            current_branch = branch_stdout.decode("utf-8", errors="replace").strip() or None

            # Get all local branches
            branches_result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "branch", "--list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            branches_stdout, _ = await branches_result.communicate()
            branches = [
                b.strip().lstrip("* ").strip()
                for b in branches_stdout.decode("utf-8", errors="replace").split("\n")
                if b.strip()
            ]

            # Get status
            status_result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "status", "--porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            status_stdout, _ = await status_result.communicate()
            status_text = status_stdout.decode("utf-8", errors="replace")

            modified = []
            staged = []
            untracked = []

            for line in status_text.split("\n"):
                if not line.strip():
                    continue
                # Git status format: XY filename
                # X = status in index (staged), Y = status in working tree (modified)
                if len(line) >= 2:
                    status_x = line[0]
                    status_y = line[1] if len(line) > 1 else " "
                    filename = line[3:] if len(line) > 3 else line[2:]

                    if status_x != " " and status_x != "?":
                        staged.append(filename)
                    if status_y != " " and status_y != "?":
                        if filename not in staged:
                            modified.append(filename)
                    if status_x == "?" or status_y == "?":
                        untracked.append(filename)

            return {
                "clean": not (modified or staged or untracked),
                "modified": modified,
                "staged": staged,
                "untracked": untracked,
                "branches": branches,
                "current_branch": current_branch,
                "not_a_git_repo": False
            }
        except Exception as e:
            logger.error(f"Git status failed: {e}")
            raise RuntimeError(f"Git status failed: {e}")


class GitCommitHandler(ToolHandler):
    """Handler for git commit command."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        import subprocess
        message = args.get("message", "")
        all_changes = args.get("all", True)
        path = args.get("path", ".")
        project_root = resolve_within_root(Path(context.get("project_root", Path.cwd())), path)

        try:
            # Stage all changes if requested
            if all_changes:
                stage_result = await asyncio.create_subprocess_exec(
                    "git", "-C", str(project_root), "add", "-A",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                _, stage_stderr = await stage_result.communicate()
                if stage_result.returncode != 0:
                    raise RuntimeError(f"Git staging failed: {stage_stderr.decode('utf-8', errors='replace')}")

            # Commit
            commit_result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "commit", "-m", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await commit_result.communicate()

            if commit_result.returncode != 0:
                # No changes to commit
                error_text = (stdout + stderr).decode("utf-8", errors="replace")
                if "nothing to commit" in error_text:
                    return {
                        "success": True,
                        "hash": None,
                        "message": "No changes to commit"
                    }
                raise RuntimeError(f"Git commit failed: {error_text}")

            # Get commit hash
            hash_result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_root), "rev-parse", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            hash_stdout, _ = await hash_result.communicate()
            commit_hash = hash_stdout.decode("utf-8", errors="replace").strip()[:12]

            return {
                "success": True,
                "hash": commit_hash,
                "message": message
            }
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            raise RuntimeError(f"Git commit failed: {e}")


class GitDiffHandler(ToolHandler):
    """Handler for git diff command."""

    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        import subprocess
        staged = args.get("staged", False)
        path = args.get("path", ".")
        project_root = resolve_within_root(Path(context.get("project_root", Path.cwd())), path)

        try:
            diff_args = ["git", "-C", str(project_root), "diff"]
            if staged:
                diff_args.append("--cached")

            result = await asyncio.create_subprocess_exec(
                *diff_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            diff_text = stdout.decode("utf-8", errors="replace")

            # Count files changed (approximate by counting lines with ---)
            files_changed = diff_text.count("--- ")

            return {
                "diff": diff_text,
                "files_changed": files_changed
            }
        except Exception as e:
            logger.error(f"Git diff failed: {e}")
            raise RuntimeError(f"Git diff failed: {e}")
