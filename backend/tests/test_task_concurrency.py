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
