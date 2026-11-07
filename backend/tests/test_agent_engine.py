"""Tests for the Agent Engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models.agent import Agent, Task, TaskStep
from app.services.agent_engine import AgentEngine, TaskStatus, StepKind
from app.services.tool_registry import BuiltInToolRegistry, Permission, get_builtin_tool_registry


class TestToolRegistry:
    """Tests for the built-in tool registry."""

    @pytest.fixture
    def registry(self):
        return BuiltInToolRegistry()

    def test_register_builtin_tools(self, registry):
        """Test that built-in tools are registered."""
        tools = registry.list_tools()
        assert len(tools) >= 7  # At least: read_file, write_file, list_files, shell, think, git_status, git_diff

        tool_names = [t.name for t in tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "shell" in tool_names
        assert "think" in tool_names
        assert "git_status" in tool_names
        assert "git_commit" in tool_names
        assert "git_diff" in tool_names

    def test_tool_permissions(self, registry):
        """Test tool permission levels."""
        read_tool = registry.get_tool("read_file")
        write_tool = registry.get_tool("write_file")
        shell_tool = registry.get_tool("shell")
        git_status_tool = registry.get_tool("git_status")
        git_commit_tool = registry.get_tool("git_commit")

        assert read_tool.permission == Permission.READ
        assert write_tool.permission == Permission.WRITE
        assert shell_tool.permission == Permission.EXECUTE
        assert git_status_tool.permission == Permission.READ
        assert git_commit_tool.permission == Permission.WRITE

    def test_has_permission(self, registry):
        """Test permission checking."""
        assert registry.has_permission("read_file", Permission.READ)
        assert not registry.has_permission("read_file", Permission.WRITE)
        assert registry.has_permission("write_file", Permission.WRITE)
        assert not registry.has_permission("read_file", Permission.EXECUTE)
        assert registry.has_permission("git_status", Permission.READ)
        assert not registry.has_permission("git_status", Permission.WRITE)
        assert registry.has_permission("git_commit", Permission.WRITE)


class TestToolHandlers:
    """Tests for individual tool handlers."""

    @pytest.fixture
    def registry(self):
        return get_builtin_tool_registry()

    @pytest.mark.asyncio
    async def test_think_handler(self, registry):
        """Test the think handler works."""
        handler = registry.get_handler("think")
        result = await handler.execute({"thought": "test reasoning"}, {})
        assert result["thought_count"] == 0

    @pytest.mark.asyncio
    async def test_git_status_handler(self, registry):
        """Test the git status handler works."""
        handler = registry.get_handler("git_status")
        result = await handler.execute({}, {"project_root": "."})
        # Should work even if not in a git repo
        assert "clean" in result
        assert "current_branch" in result

    @pytest.mark.asyncio
    async def test_git_diff_handler(self, registry):
        """Test the git diff handler works."""
        handler = registry.get_handler("git_diff")
        result = await handler.execute({"staged": False}, {"project_root": "."})
        assert "diff" in result
        assert "files_changed" in result


class TestContextManager:
    """Tests for the context manager."""

    @pytest.mark.asyncio
    async def test_context_set_task(self):
        """Test setting task context."""
        from app.services.context_manager import ContextManager

        cm = ContextManager()
        cm.set_task_context(
            task_id="1",
            title="Test Task",
            description="A test task",
            goals=["Goal 1", "Goal 2"],
            constraints=["Constraint 1"]
        )

        assert cm.get_task_info() is not None
        assert cm.get_task_info()["title"] == "Test Task"

        messages = cm.messages
        assert len(messages) >= 1
        assert messages[0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_context_compaction(self):
        """Test that context compacts when near limit."""
        from app.services.context_manager import ContextManager

        cm = ContextManager(max_tokens=500, reserved_tokens=100)

        # Build up messages
        for i in range(20):
            cm.add_message("user", f"Message {i}" * 50)

        # Should have compacted
        assert len(cm.messages) < 20


class TestAgentEngine:
    """Tests for the agent engine."""

    @pytest.fixture
    def engine(self):
        return AgentEngine()

    @pytest.mark.asyncio
    async def test_parse_action(self, engine):
        """Test action parsing from thought output."""
        thought = """
        THOUGHT: I need to read a file
        ACTION: read_file{"path": "test.txt", "options": {"encoding": "utf-8"}}
        OBSERVATION: {content: "test content"}
        """
        action = engine._parse_action(thought)
        assert action is not None
        assert action["tool"] == "read_file"
        assert action["args"] == {"path": "test.txt", "options": {"encoding": "utf-8"}}

    @pytest.mark.asyncio
    async def test_should_terminate(self, engine):
        """Test termination detection."""
        thought1 = "COMPLETE: Task finished successfully"
        assert engine._should_terminate(thought1)

        thought2 = "Just thinking..."
        assert not engine._should_terminate(thought2)

    @pytest.mark.asyncio
    async def test_plan_step_format(self, engine):
        """Require an explicit final answer marker before completing."""
        assert engine._completion_result("COMPLETE: all done") == "all done"
        assert engine._completion_result("THOUGHT: still working") is None


class TestTaskService:
    """Tests for the task service."""

    @pytest.mark.asyncio
    async def test_task_status_enum(self):
        """Test task status values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
