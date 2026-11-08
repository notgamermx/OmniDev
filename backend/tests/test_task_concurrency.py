"""Exercise lifecycle races against real SQLite and independent engine instances."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models.agent import Agent
from app.services.agent_engine import AgentEngine, ExecutionContext
from app.services.background_tasks import BackgroundTaskManager


async def create_task():
    import app.services.agent_engine as module

    with module.SessionLocal() as db:
        agent = Agent(
            name="race-agent", created_at="now", updated_at="now", tool_names=[]
        )
        db.add(agent)
        db.commit()
        agent_id = agent.id
    return await AgentEngine().create_task(agent_id, "Execute once")


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_two_workers_execute_same_pending_task_once(
    isolated_service_db, tmp_path, stream
):
    task = await create_task()
    barrier = threading.Barrier(2)
    executed = []

    def worker():
        engine = AgentEngine()
        original_load = engine.load_task

        async def load(task_id):
            loaded = await original_load(task_id)
            # Both workers must read pending before either claims the row.
            assert loaded.status == "pending"
            await asyncio.to_thread(barrier.wait, 5)
            return loaded

        async def steps(context):
            executed.append(context.task_model.id)
            await engine._persist_task(context, status="completed", result="done")
            yield {"type": "complete"}

        engine.load_task = load
        engine._run_steps = steps

        async def run():
            try:
                result = await engine.execute_task(
                    task.id, str(tmp_path), stream=stream
                )
                if stream:
                    return [event async for event in result]
                return result
            except ValueError as exc:
                return exc

        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = await asyncio.gather(
            *(asyncio.wrap_future(pool.submit(worker)) for _ in range(2))
        )
    assert len(executed) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    assert (await AgentEngine().load_task(task.id)).status == "completed"


@pytest.mark.asyncio
async def test_cancelled_task_cannot_be_claimed_or_completed(
    isolated_service_db, tmp_path
):
    task = await create_task()
    engine = AgentEngine()
    agent = await engine.load_agent(task.agent_id)
    stale = ExecutionContext(agent, task, str(tmp_path))
    assert await AgentEngine().cancel_task(task.id)
    with pytest.raises(ValueError, match="pending"):
        await engine._claim_task(stale)
    await engine._persist_task(stale, status="completed", result="late success")
    current = await engine.load_task(task.id)
    assert current.status == "cancelled" and current.result is None
    assert stale.task_model.status == "cancelled"
    assert not await engine.cancel_task(task.id)


@pytest.mark.asyncio
async def test_engine_coroutine_cancellation_persists_and_releases_owner(
    isolated_service_db, tmp_path
):
    task = await create_task()
    engine = AgentEngine()
    entered = asyncio.Event()
    cleaned = asyncio.Event()

    async def steps(context):
        try:
            entered.set()
            await asyncio.Event().wait()
            yield {}
        finally:
            cleaned.set()

    engine._run_steps = steps
    running = asyncio.create_task(engine.execute_task(task.id, str(tmp_path)))
    await asyncio.wait_for(entered.wait(), 5)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert cleaned.is_set()
    assert not engine._running_tasks
    assert (await engine.load_task(task.id)).status == "cancelled"


@pytest.mark.asyncio
async def test_background_success_failure_and_callback():
    manager = BackgroundTaskManager()
    gate = asyncio.Event()
    called = []

    async def success():
        await gate.wait()
        return 42

    async def failure():
        raise ValueError("expected failure")

    good = await manager.submit("success", success(), called.append)
    bad = await manager.submit("failure", failure())
    assert (await manager.list_tasks())[good] == "running"
    gate.set()
    await asyncio.gather(*list(manager._tasks.values()))
    assert (await manager.list_tasks()) == {good: "completed", bad: "failed"}
    assert await manager.get_result(good) == 42 and called == [42]
    assert (await manager.get_result(bad))["type"] == "ValueError"
    assert not await manager.cancel(good)
    assert not manager._tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("before_start", [False, True])
async def test_background_cancel_waits_for_cleanup_and_closes_unstarted_coroutine(
    before_start,
):
    import inspect

    manager = BackgroundTaskManager()
    entered = asyncio.Event()
    cleaned = asyncio.Event()

    async def work():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    coroutine = work()
    task_id = await manager.submit("cancel", coroutine)
    if not before_start:
        await asyncio.wait_for(entered.wait(), 5)
    assert await manager.cancel(task_id)
    assert (await manager.list_tasks())[task_id] == "cancelled"
    assert await manager.get_result(task_id) == {"cancelled": True}
    assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
    assert cleaned.is_set() == (not before_start)
    assert not manager._tasks
    assert not await manager.cancel(task_id)


@pytest.mark.asyncio
async def test_cancel_during_verification_does_not_report_completion(
    isolated_service_db, tmp_path
):
    from app.services.agent_engine import ToolResult
    import app.services.agent_engine as module

    task = await create_task()
    with module.SessionLocal() as db:
        row = db.get(module.TaskModel, task.id)
        row.task_config = {"verification_command": "echo check"}
        db.commit()
    engine = AgentEngine()
    entered, release = asyncio.Event(), asyncio.Event()

    async def plan(context):
        return "COMPLETE: done"

    async def verify(context, action):
        entered.set()
        await release.wait()
        return ToolResult("shell", True, {"exit_code": 0, "timed_out": False})

    engine._plan_step = plan
    engine._execute_action = verify

    async def run():
        return [
            event
            async for event in await engine.execute_task(
                task.id, str(tmp_path), stream=True
            )
        ]

    running = asyncio.create_task(run())
    await asyncio.wait_for(entered.wait(), 5)
    assert await AgentEngine().cancel_task(task.id)
    release.set()
    events = await asyncio.wait_for(running, 5)
    assert events[-1]["type"] == "cancelled"
    assert not any(event["type"] == "complete" for event in events)
    assert (await engine.load_task(task.id)).status == "cancelled"


@pytest.mark.asyncio
async def test_closing_started_stream_cancels_task_and_releases_owner(isolated_service_db, tmp_path):
    task = await create_task()
    engine = AgentEngine()
    stream = await engine.execute_task(task.id, str(tmp_path), stream=True)
    assert (await anext(stream))["type"] == "status"
    await stream.aclose()
    assert not engine._running_tasks
    assert (await engine.load_task(task.id)).status == "cancelled"

@pytest.mark.asyncio
async def test_losing_service_starter_does_not_fail_the_claimed_task(isolated_service_db, tmp_path):
    from app.services.task_service import TaskService
    from unittest.mock import AsyncMock
    task = await create_task()
    engine = AgentEngine()
    context = ExecutionContext(await engine.load_agent(task.agent_id), task, str(tmp_path))
    async def lose(*args):
        await engine._claim_task(context)
        raise ValueError("Another worker owns this task")
    engine.execute_task = AsyncMock(side_effect=lose)
    with pytest.raises(ValueError):
        await TaskService(engine).start_task(task.id, str(tmp_path))
    assert (await engine.load_task(task.id)).status == "running"

@pytest.mark.asyncio
async def test_terminal_states_cannot_be_reopened(isolated_service_db, tmp_path):
    task = await create_task()
    engine = AgentEngine()
    context = ExecutionContext(await engine.load_agent(task.agent_id), task, str(tmp_path))
    with pytest.raises(ValueError, match="Invalid task transition"):
        await engine._persist_task(context, status="completed")
    await engine._claim_task(context)
    await engine._persist_task(context, status="verifying")
    await engine._persist_task(context, status="completed", result="verified")
    await engine._persist_task(context, status="running")
    assert (await engine.load_task(task.id)).status == "completed"

@pytest.mark.asyncio
async def test_persistent_cancellation_interrupts_inflight_operation(isolated_service_db, tmp_path):
    task = await create_task()
    engine = AgentEngine()
    context = ExecutionContext(await engine.load_agent(task.agent_id), task, str(tmp_path))
    await engine._claim_task(context)
    entered, cleaned = asyncio.Event(), asyncio.Event()
    async def operation():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleaned.set()
    work = asyncio.create_task(engine._interruptible(operation(), context))
    await entered.wait()
    await AgentEngine().cancel_task(task.id)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(work, 2)
    assert cleaned.is_set()

@pytest.mark.asyncio
async def test_pause_and_resume_preserve_existing_worker(isolated_service_db, tmp_path, monkeypatch):
    from app.api.v1.endpoints import tasks
    from app.services.task_service import TaskService
    task = await create_task()
    engine = AgentEngine()
    context = ExecutionContext(await engine.load_agent(task.agent_id), task, str(tmp_path))
    await engine._claim_task(context)
    monkeypatch.setattr(tasks, "get_task_service", lambda: TaskService(engine))
    await engine._persist_task(context, step_count=3)
    assert (await tasks.pause_task(task.id, True))["status"] == "paused"
    waiting = asyncio.create_task(engine._wait_if_paused(context))
    await asyncio.sleep(0)
    assert not waiting.done()
    await tasks.pause_task(task.id, False)
    await asyncio.wait_for(waiting, 2)
    assert (await engine.load_task(task.id)).status == "running"
    history = await TaskService(engine).get_task_steps(task.id)
    assert [event.step_index for event in history] == [0, 3, 3]
    assert '"to": "paused"' in history[-2].content
    assert '"to": "running"' in history[-1].content


@pytest.mark.asyncio
async def test_restart_recovery_marks_inflight_work_failed_without_replay(isolated_service_db):
    from app.main import recover_interrupted_tasks
    import app.services.agent_engine as module
    task = await create_task()
    with module.SessionLocal() as db:
        row = db.get(module.TaskModel, task.id)
        row.status = "verifying"
        db.commit()
        recover_interrupted_tasks(db)
        db.refresh(row)
        assert row.status == "failed" and "review" in row.error
        events = db.query(module.TaskStepModel).filter_by(task_id=task.id, kind="state").all()
        assert len(events) == 1 and "engine_restart" in events[0].content


@pytest.mark.asyncio
async def test_pause_at_completion_boundary_waits_for_resume(isolated_service_db, tmp_path, monkeypatch):
    from app.api.v1.endpoints import tasks
    from app.services.task_service import TaskService

    task = await create_task()
    engine = AgentEngine()
    context = ExecutionContext(await engine.load_agent(task.agent_id), task, str(tmp_path))
    await engine._claim_task(context)
    monkeypatch.setattr(tasks, "get_task_service", lambda: TaskService(engine))
    await tasks.pause_task(task.id, True)
    completing = asyncio.create_task(engine._persist_task(context, status="completed", result="done"))
    await asyncio.sleep(0.05)
    assert not completing.done()
    assert (await engine.load_task(task.id)).status == "paused"
    await tasks.pause_task(task.id, False)
    await asyncio.wait_for(completing, 2)
    current = await engine.load_task(task.id)
    assert current.status == "completed" and current.result == "done"
