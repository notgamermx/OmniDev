import asyncio
from types import SimpleNamespace

import pytest

from app.services.agent_engine import AgentEngine, TaskStatus
from app.services.context_manager import ContextManager
from app.services.tool_registry import BuiltInToolRegistry


class FakeProvider:
    def __init__(self, responses, calls, closed):
        self.responses = responses
        self.calls = calls
        self.closed = closed

    async def chat_completion(self, **kwargs):
        self.calls.append(kwargs["messages"])
        content = next(self.responses)
        return {"choices": [{"message": {"content": content}}]}

    async def close(self):
        self.closed.append(True)


def make_task(task_id=1, max_steps=4):
    return SimpleNamespace(
        id=task_id,
        status="pending",
        agent_id=7,
        title="Test task",
        description="A test task",
        plan=["Think through the task", "Finish it"],
        task_config={"constraints": ["Stay in project root"]},
        max_steps=max_steps,
        step_count=0,
        result=None,
        error=None,
        updated_at=None,
    )


def make_agent():
    return SimpleNamespace(
        id=7,
        name="test-agent",
        enabled=True,
        provider="google_gemini",
        model="test-model",
        temperature=0.0,
        system_prompt="Be concise.",
        tool_names=["think"],
    )


def prepare_engine(monkeypatch, task, responses):
    engine = AgentEngine(BuiltInToolRegistry())
    calls = []
    closed = []
    records = []
    response_iter = iter(responses)

    monkeypatch.setattr(engine, "load_task", lambda task_id: _return(task))
    monkeypatch.setattr(engine, "load_agent", lambda agent_id: _return(make_agent()))

    async def persist(context, **changes):
        for key, value in changes.items():
            setattr(context.task_model, key, value)

    async def record(context, kind, content, **kwargs):
        records.append((kind.value, content, kwargs))

    async def not_cancelled(context):
        return False

    monkeypatch.setattr(engine, "_persist_task", persist)
    monkeypatch.setattr(engine, "_record_step", record)
    monkeypatch.setattr(engine, "_cancel_requested", not_cancelled)
    monkeypatch.setattr(
        "app.services.agent_engine.make_provider",
        lambda provider: FakeProvider(response_iter, calls, closed),
    )
    return engine, calls, closed, records


async def _return(value):
    return value


@pytest.mark.asyncio
async def test_agent_executes_tool_and_uses_observation_in_next_plan(monkeypatch):
    task = make_task()
    engine, calls, closed, records = prepare_engine(
        monkeypatch,
        task,
        [
            'THOUGHT: reflect first\nACTION: think {"thought":"inspect the goal","context":"stage 1"}',
            "THOUGHT: the tool returned its observation\nCOMPLETE: Task finished",
        ],
    )

    result = await engine.execute_task(task.id, project_root=".")

    assert result.status == TaskStatus.COMPLETED.value
    assert result.result == "Task finished"
    assert result.step_count == 2
    assert any(kind == "action" for kind, _, _ in records)
    assert any(kind == "observation" for kind, _, _ in records)
    assert calls[1][-2]["role"] == "assistant"
    assert "ACTION: think" in calls[1][-2]["content"]
    assert calls[1][-1]["role"] == "user"
    assert "inspect the goal" in calls[1][-1]["content"]
    assert len(closed) == 2


@pytest.mark.asyncio
async def test_streamed_execution_yields_completion_and_updates_state(monkeypatch):
    task = make_task(task_id=2)
    engine, _, _, _ = prepare_engine(monkeypatch, task, ["COMPLETE: Streamed task finished"])

    events = [event async for event in await engine.execute_task(task.id, stream=True)]

    assert events[0]["type"] == "status"
    assert events[-1] == {
        "type": "complete",
        "task_id": task.id,
        "result": "Streamed task finished",
    }
    assert task.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_reaching_step_limit_fails_instead_of_reporting_success(monkeypatch):
    task = make_task(task_id=3, max_steps=1)
    engine, _, _, _ = prepare_engine(monkeypatch, task, ["THOUGHT: still working"])

    result = await engine.execute_task(task.id)

    assert result.status == TaskStatus.FAILED.value
    assert "Maximum step count" in result.error


def test_tool_arguments_are_validated_and_shell_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr("app.services.tool_registry.settings.TERMINAL_ENABLED", False)
    registry = BuiltInToolRegistry()
    assert not registry.is_enabled("shell")
    assert registry.validate_args("think", {"thought": "plan"}) == (True, "")
    valid, error = registry.validate_args("think", {"thought": 4})
    assert not valid
    assert "must be string" in error


def test_agent_and_task_endpoint_service_getters_resolve():
    from app.api.v1.endpoints.agents import get_agent_service
    from app.api.v1.endpoints.tasks import get_task_service
    from app.services.agent_service import AgentService
    from app.services.task_service import TaskService

    assert isinstance(get_agent_service(), AgentService)
    assert isinstance(get_task_service(), TaskService)


def test_agent_task_routes_have_single_prefix():
    from app.api.v1.endpoints import agents, tasks

    assert agents.router.prefix == ""
    assert tasks.router.prefix == ""


def test_context_compaction_retains_task_prompt_and_recent_observation():
    context = ContextManager(max_tokens=300, reserved_tokens=50, preserve_first_n=1)
    context.set_task_context(task_id="4", title="Keep this task", goals=["Finish safely"])
    context.add_message("system", "Only use assigned tools.")
    for index in range(12):
        context.add_message("user", f"observation {index}: " + ("x" * 80))

    assert "Keep this task" in context.messages[0]["content"]
    assert "observation 11" in context.messages[-1]["content"]
    assert context.current_tokens + context.reserved_tokens <= context.max_tokens


@pytest.mark.asyncio
async def test_cancel_marks_running_task_and_signals_execution(monkeypatch):
    task = SimpleNamespace(id=5, status=TaskStatus.RUNNING.value)
    context = SimpleNamespace(cancel_event=asyncio.Event())
    engine = AgentEngine()
    engine._running_tasks[task.id] = context

    class FakeDb:
        def get(self, model, task_id):
            return task if task_id == task.id else None

        def commit(self):
            pass

    async def with_db(operation):
        return operation(FakeDb())

    monkeypatch.setattr(engine, "_with_db", with_db)
    assert await engine.cancel_task(task.id)
    assert task.status == TaskStatus.CANCELLED.value
    assert context.cancel_event.is_set()
