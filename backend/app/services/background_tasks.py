"""Background task manager for managing async tasks."""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Coroutine

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background async tasks with lifecycle tracking."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def submit(self, name: str, coro: Coroutine, callback: Optional[Callable[[Any], None]] = None) -> str:
        """Submit a background task and return its ID."""
        async with self._lock:
            task_id = str(uuid.uuid4())
            task = asyncio.create_task(self._run_task(task_id, name, coro, callback))
            self._tasks[task_id] = task
            logger.info(f"Submitted background task: {task_id} - {name}")
            return task_id

    async def _run_task(self, task_id: str, name: str, coro: Coroutine, callback: Optional[Callable[[Any], None]]) -> None:
        """Run a background task with error handling and result capture."""
        try:
            result = await coro
            self._results[task_id] = result
            if callback:
                callback(result)
            logger.debug(f"Background task completed: {task_id} - {name}")
        except Exception as e:
            self._results[task_id] = {"error": str(e), "type": type(e).__name__}
            logger.error(f"Background task failed: {task_id} - {name}: {e}")
        finally:
            async with self._lock:
                self._tasks.pop(task_id, None)

    async def get_result(self, task_id: str) -> Optional[Any]:
        """Get the result of a completed task."""
        async with self._lock:
            return self._results.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a background task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and not task.done():
                task.cancel()
                self._tasks.pop(task_id, None)
                self._results.pop(task_id, None)
                logger.info(f"Cancelled background task: {task_id}")
                return True
            return False

    async def list_tasks(self) -> Dict[str, str]:
        """List all task IDs and their status."""
        async with self._lock:
            return {
                task_id: task.status()
                for task_id, task in self._tasks.items()
            }