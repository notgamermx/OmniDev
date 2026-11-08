"""Background task manager for managing async tasks."""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable, Coroutine

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background async tasks with lifecycle tracking."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._states: Dict[str, str] = {}

    async def submit(
        self,
        name: str,
        coro: Coroutine,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> str:
        """Submit a background task and return its ID."""
        async with self._lock:
            task_id = str(uuid.uuid4())
            started = False

            async def run():
                nonlocal started
                started = True
                await self._run_task(task_id, name, coro, callback)

            def finished(task):
                # A task cancelled before its first turn never enters the runner.
                if not started:
                    coro.close()
                self._tasks.pop(task_id, None)
                if task.cancelled():
                    self._states[task_id] = "cancelled"
                    self._results[task_id] = {"cancelled": True}

            task = asyncio.create_task(run(), name=name)
            task.add_done_callback(finished)
            self._states[task_id] = "running"
            self._tasks[task_id] = task
            logger.info(f"Submitted background task: {task_id} - {name}")
            return task_id

    async def _run_task(
        self,
        task_id: str,
        name: str,
        coro: Coroutine,
        callback: Optional[Callable[[Any], None]],
    ) -> None:
        """Run a background task with error handling and result capture."""
        try:
            result = await coro
            self._results[task_id] = result
            if callback:
                callback(result)
            self._states[task_id] = "completed"
            logger.debug(f"Background task completed: {task_id} - {name}")
        except Exception as e:
            self._states[task_id] = "failed"
            self._results[task_id] = {"error": str(e), "type": type(e).__name__}
            logger.error(f"Background task failed: {task_id} - {name}: {e}")

    async def get_result(self, task_id: str) -> Optional[Any]:
        """Get the result of a completed task."""
        async with self._lock:
            return self._results.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a background task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.done():
                return False
            task.cancel()
        # Await cleanup without holding the lock needed by other callers.
        await asyncio.gather(task, return_exceptions=True)
        logger.info(f"Cancelled background task: {task_id}")
        return True

    async def list_tasks(self) -> Dict[str, str]:
        """List submitted tasks, including completed and cancelled tasks."""
        async with self._lock:
            return dict(self._states)
