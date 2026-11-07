"""Task planning and tool execution loop for configured agents."""

import asyncio
import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.agent import (
    Agent as AgentModel,
    Task as TaskModel,
    TaskStep as TaskStepModel,
)
from app.services.context_manager import ContextManager
from app.services.llm_providers import make_provider, ProviderError
from app.core.config import settings
from app.services.tool_registry import (
    BuiltInToolRegistry,
    Permission,
    get_builtin_tool_registry,
)

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepKind(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ExecutionContext:
    agent_model: AgentModel
    task_model: TaskModel
    project_root: str
    step_count: int = 0
    context_manager: ContextManager = field(default_factory=ContextManager)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class AgentEngine:
    """Run a bounded ReAct loop and persist each decision and tool result."""

    def __init__(self, tool_registry: Optional[BuiltInToolRegistry] = None) -> None:
        self.tool_registry = tool_registry or get_builtin_tool_registry()
        self._running_tasks: dict[int, ExecutionContext] = {}

    async def _with_db(self, operation):
        db = SessionLocal()
        try:
            result = operation(db)
            return await result if inspect.isawaitable(result) else result
        finally:
            db.close()

    async def load_agent(self, agent_id: int) -> AgentModel:
        def op(db):
            return db.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            ).scalar_one_or_none()

        agent = await self._with_db(op)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        return agent

    async def load_task(self, task_id: int) -> TaskModel:
        def op(db):
            return db.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            ).scalar_one_or_none()

        task = await self._with_db(op)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        return task

    async def create_task(
        self,
        agent_id: int,
        title: str,
        description: Optional[str] = None,
        project_id: Optional[int] = None,
        max_steps: int = 25,
        goals: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
    ) -> TaskModel:
        def op(db):
            if db.get(AgentModel, agent_id) is None:
                raise ValueError(f"Agent {agent_id} not found")
            task = TaskModel(
                agent_id=agent_id,
                project_id=project_id,
                title=title,
                description=description,
                status=TaskStatus.PENDING.value,
                priority="normal",
                plan=goals or [],
                max_steps=max(1, max_steps),
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                task_config={"constraints": constraints or []},
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task

        return await self._with_db(op)

    async def _persist_task(self, context: ExecutionContext, **changes: Any) -> None:
        def op(db):
            task = db.get(TaskModel, context.task_model.id)
            if task is None:
                raise ValueError(f"Task {context.task_model.id} not found")
            for name, value in changes.items():
                setattr(task, name, value)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()

        await self._with_db(op)
        for name, value in changes.items():
            setattr(context.task_model, name, value)
        context.task_model.updated_at = datetime.now(timezone.utc).isoformat()

    async def execute_task(
        self, task_id: int, project_root: str = ".", stream: bool = False
    ):
        task = await self.load_task(task_id)
        if task.status != TaskStatus.PENDING.value:
            raise ValueError(
                f"Task {task_id} must be pending to start (current status: {task.status})"
            )
        agent = await self.load_agent(task.agent_id)
        if not agent.enabled:
            raise ValueError(f"Agent {agent.id} is disabled")
        context = ExecutionContext(
            agent_model=agent, task_model=task, project_root=project_root
        )

        context.context_manager.set_task_context(
            task_id=str(task.id),
            title=task.title,
            description=task.description,
            goals=task.plan,
            constraints=(task.task_config or {}).get("constraints", []),
        )
        if task.project_id is not None:
            from app.services.memory_service import get_memory_service

            memory = get_memory_service()
            entries = await memory.list_project_memories(task.project_id)
            understanding = await memory.get_project_understanding(task.project_id)
            context.context_manager.add_message(
                "system",
                "Project memory (reference data): "
                + json.dumps(
                    {
                        "memories": [
                            {"key": m.key, "value": m.value} for m in entries[:20]
                        ],
                        "understanding": understanding.understanding
                        if understanding
                        else None,
                    },
                    default=str,
                )[:12000],
            )
        tools = [
            tool
            for tool in self.tool_registry.list_tools()
            if tool.name in (agent.tool_names or [])
            and self.tool_registry.is_enabled(tool.name)
        ]
        context.context_manager.add_message(
            "system",
            json.dumps(
                {
                    "agent_instructions": agent.system_prompt,
                    "response_format": "Return THOUGHT and either ACTION: tool_name {JSON arguments} or COMPLETE: final result.",
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "permission": tool.permission.value,
                            "input_schema": tool.input_schema,
                        }
                        for tool in tools
                    ],
                }
            ),
        )

        await self._persist_task(
            context,
            status=TaskStatus.RUNNING.value,
            error=None,
            result=None,
            step_count=0,
        )
        self._running_tasks[task_id] = context
        if stream:
            return self._execute_streaming(context)

        try:
            async for _ in self._run_steps(context):
                pass
            return context.task_model
        except asyncio.CancelledError:
            await self._persist_task(context, status=TaskStatus.CANCELLED.value)
            raise
        except Exception as exc:
            logger.exception("Task %s failed", task_id)
            await self._persist_task(
                context, status=TaskStatus.FAILED.value, error=str(exc)
            )
            raise
        finally:
            self._running_tasks.pop(task_id, None)

    async def _execute_streaming(
        self, context: ExecutionContext
    ) -> AsyncIterator[dict[str, Any]]:
        task_id = context.task_model.id
        try:
            yield {
                "type": "status",
                "status": TaskStatus.RUNNING.value,
                "task_id": task_id,
            }
            async for event in self._run_steps(context):
                yield event
        except asyncio.CancelledError:
            await self._persist_task(context, status=TaskStatus.CANCELLED.value)
            raise
        except Exception:
            logger.exception("Streaming task %s failed", task_id)
            await self._persist_task(
                context, status=TaskStatus.FAILED.value, error="Task execution failed"
            )
            yield {
                "type": "error",
                "task_id": task_id,
                "message": "Task execution failed",
            }
        finally:
            self._running_tasks.pop(task_id, None)

    async def _run_steps(
        self, context: ExecutionContext
    ) -> AsyncIterator[dict[str, Any]]:
        task = context.task_model
        max_steps = max(1, task.max_steps or 25)
        for step_index in range(1, max_steps + 1):
            if await self._cancel_requested(context):
                await self._persist_task(
                    context,
                    status=TaskStatus.CANCELLED.value,
                    step_count=context.step_count,
                )
                yield {
                    "type": "cancelled",
                    "task_id": task.id,
                    "step": context.step_count,
                }
                return

            context.step_count = step_index
            context.context_manager.update_step_count()
            await self._persist_task(context, step_count=step_index)
            thought = await self._plan_step(context)
            if await self._cancel_requested(context):
                await self._persist_task(
                    context, status=TaskStatus.CANCELLED.value, step_count=step_index
                )
                yield {"type": "cancelled", "task_id": task.id, "step": step_index}
                return
            context.context_manager.add_thought(thought)
            context.context_manager.add_message("assistant", thought)
            await self._record_step(context, StepKind.THOUGHT, thought)
            yield {
                "type": "thought",
                "task_id": task.id,
                "step": step_index,
                "content": thought,
            }

            completion = self._completion_result(thought)
            if completion is not None:
                verification = (task.task_config or {}).get("verification_command")
                if verification:
                    result = await self._execute_action(
                        context,
                        {
                            "tool": "shell",
                            "args": {"command": verification, "timeout": 120},
                        },
                    )
                    output = json.dumps(result.to_dict(), default=str)
                    await self._record_step(
                        context,
                        StepKind.OBSERVATION,
                        output,
                        tool_name="shell",
                        tool_result=output,
                        error=result.error,
                    )
                    yield {
                        "type": "verification",
                        "task_id": task.id,
                        "result": result.to_dict(),
                    }
                    if (
                        not result.success
                        or result.result.get("exit_code") != 0
                        or result.result.get("timed_out")
                    ):
                        context.context_manager.add_message(
                            "user",
                            "Verification failed; fix the project before completing: "
                            + output,
                        )
                        continue
                await self._persist_task(
                    context,
                    status=TaskStatus.COMPLETED.value,
                    result=completion,
                    error=None,
                    step_count=step_index,
                )
                if task.project_id is not None:
                    try:
                        from app.services.memory_service import get_memory_service

                        await get_memory_service().set_project_memory(
                            task.project_id,
                            f"task:{task.id}",
                            value=completion[:12000],
                            importance=10,
                        )
                    except Exception:
                        logger.exception(
                            "Could not save task summary to project memory"
                        )
                yield {"type": "complete", "task_id": task.id, "result": completion}
                return

            action = self._parse_action(thought)
            if action is None:
                await self._record_step(
                    context,
                    StepKind.DECISION,
                    "No tool action returned; continuing plan.",
                )
                continue

            await self._record_step(
                context,
                StepKind.ACTION,
                json.dumps(action, ensure_ascii=False),
                tool_name=action["tool"],
                tool_args=action["args"],
            )
            yield {"type": "action", "task_id": task.id, "step": step_index, **action}

            result = await self._execute_action(context, action)
            await self._record_step(
                context,
                StepKind.OBSERVATION,
                json.dumps(result.to_dict(), ensure_ascii=False, default=str),
                tool_name=result.tool_name,
                tool_args=action["args"],
                tool_result=json.dumps(result.result, ensure_ascii=False, default=str),
                error=result.error,
            )
            context.context_manager.add_message(
                "user",
                "Tool observation: "
                + json.dumps(result.to_dict(), ensure_ascii=False, default=str),
            )
            yield {
                "type": "result",
                "task_id": task.id,
                "step": step_index,
                "result": result.to_dict(),
            }
            if await self._cancel_requested(context):
                await self._persist_task(
                    context, status=TaskStatus.CANCELLED.value, step_count=step_index
                )
                yield {"type": "cancelled", "task_id": task.id, "step": step_index}
                return

        message = (
            f"Maximum step count ({max_steps}) reached without a completion response."
        )
        await self._persist_task(
            context, status=TaskStatus.FAILED.value, error=message, step_count=max_steps
        )
        yield {"type": "error", "task_id": task.id, "message": message}

    async def _cancel_requested(self, context: ExecutionContext) -> bool:
        if context.cancel_event.is_set():
            return True

        def op(db):
            task = db.get(TaskModel, context.task_model.id)
            return task is None or task.status == TaskStatus.CANCELLED.value

        return await self._with_db(op)

    async def cancel_task(self, task_id: int) -> bool:
        context = self._running_tasks.get(task_id)
        if context is not None:
            context.cancel_event.set()

        def op(db):
            task = db.get(TaskModel, task_id)
            if task is None or task.status in {
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            }:
                return False
            task.status = TaskStatus.CANCELLED.value
            task.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return True

        return await self._with_db(op)

    async def _plan_step(self, context: ExecutionContext) -> str:
        candidates = [
            {
                "provider": context.agent_model.provider,
                "model": context.agent_model.model,
            }
        ] + settings.PROVIDER_FALLBACKS
        last_error = None
        for candidate in candidates:
            provider = None
            try:
                provider = make_provider(candidate["provider"])
                response = await provider.chat_completion(
                    model=candidate["model"],
                    messages=context.context_manager.get_prompt(),
                    temperature=context.agent_model.temperature or 0.0,
                    max_tokens=2000,
                )
                content = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not isinstance(content, str):
                    raise ValueError("Provider returned a non-text planning response")
                return content.strip()
            except ProviderError as exc:
                last_error = exc
            finally:
                if provider is not None:
                    await provider.close()
        raise last_error or ProviderError("No provider available")

    @staticmethod
    def _parse_action(thought: str) -> Optional[dict[str, Any]]:
        match = re.search(r"(?m)^\s*ACTION:\s*([\w.-]+)\s*", thought)
        if not match:
            return None
        start = thought.find("{", match.end())
        if start < 0:
            return None

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(thought)):
            char = thought[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        args = json.loads(thought[start : index + 1])
                    except json.JSONDecodeError:
                        return None
                    return (
                        {"tool": match.group(1), "args": args}
                        if isinstance(args, dict)
                        else None
                    )
        return None

    @staticmethod
    def _completion_result(thought: str) -> Optional[str]:
        match = re.search(r"(?im)^\s*COMPLETE:\s*(.*)$", thought)
        return match.group(1).strip() if match else None

    @classmethod
    def _should_terminate(cls, thought: str) -> bool:
        return cls._completion_result(thought) is not None

    async def _execute_action(
        self, context: ExecutionContext, action: dict[str, Any]
    ) -> ToolResult:
        tool_name = action["tool"]
        args = action["args"]
        if tool_name not in (context.agent_model.tool_names or []):
            return ToolResult(
                tool_name,
                False,
                None,
                f"Tool '{tool_name}' is not assigned to this agent",
            )
        if not self.tool_registry.is_enabled(tool_name):
            return ToolResult(tool_name, False, None, f"Tool '{tool_name}' is disabled")
        tool_def = self.tool_registry.get_tool(tool_name)
        if tool_def is None or not self.tool_registry.has_permission(
            tool_name, tool_def.permission
        ):
            return ToolResult(
                tool_name, False, None, f"Permission denied for tool '{tool_name}'"
            )
        valid, error = self.tool_registry.validate_args(tool_name, args)
        if not valid:
            return ToolResult(tool_name, False, None, error)
        handler = self.tool_registry.get_handler(tool_name)
        if handler is None:
            return ToolResult(
                tool_name, False, None, f"No handler for tool '{tool_name}'"
            )

        try:
            result = await handler.execute(
                args,
                {
                    "project_root": context.project_root,
                    "task_id": context.task_model.id,
                    "agent_name": context.agent_model.name,
                },
            )
            return ToolResult(tool_name, True, result)
        except Exception as exc:
            logger.warning(
                "Tool execution failed for %s: %s", tool_name, type(exc).__name__
            )
            return ToolResult(tool_name, False, None, str(exc))

    async def _record_step(
        self,
        context: ExecutionContext,
        kind: StepKind,
        content: str,
        *,
        tool_name: Optional[str] = None,
        tool_args: Optional[dict[str, Any]] = None,
        tool_result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        def op(db):
            db.add(
                TaskStepModel(
                    task_id=context.task_model.id,
                    step_index=context.step_count,
                    kind=kind.value,
                    content=content,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=tool_result,
                    error=error,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            db.commit()

        await self._with_db(op)

    async def get_task_status(self, task_id: int) -> dict[str, Any]:
        def op(db):
            task = db.get(TaskModel, task_id)
            if task is None:
                return {"error": f"Task {task_id} not found"}
            return {
                "task_id": task.id,
                "title": task.title,
                "status": task.status,
                "max_steps": task.max_steps,
                "current_step": task.step_count,
                "result": task.result,
                "error": task.error,
            }

        return await self._with_db(op)


__all__ = [
    "AgentEngine",
    "ExecutionContext",
    "TaskStatus",
    "StepKind",
    "ToolResult",
    "get_builtin_tool_registry",
]
