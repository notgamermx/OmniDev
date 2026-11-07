"""Task service for managing task lifecycle."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from sqlalchemy import select, delete

from app.database.session import SessionLocal
from app.models.agent import Agent, Task, TaskStep
from app.services.agent_engine import AgentEngine, TaskStatus

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks and their execution."""

    def __init__(self, agent_engine: Optional[AgentEngine] = None) -> None:
        self.agent_engine = agent_engine or AgentEngine()

    def _with_db(self, operation):
        """Execute an operation with a database session."""
        db = SessionLocal()
        try:
            return operation(db)
        finally:
            db.close()

    async def create_task(
        self,
        agent_id: int,
        title: str,
        description: Optional[str] = None,
        project_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        max_steps: int = 25,
        goals: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        verification_command: Optional[str] = None,
    ) -> Task:
        """Create a new task."""

        def op(db):
            # Verify agent exists
            agent = db.execute(
                select(Agent).where(Agent.id == agent_id)
            ).scalar_one_or_none()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            if verification_command:
                from app.core.config import settings

                if not settings.TERMINAL_ENABLED or "shell" not in (
                    agent.tool_names or []
                ):
                    raise ValueError(
                        "Verification requires TERMINAL_ENABLED and an agent with the shell tool"
                    )
            task = Task(
                agent_id=agent_id,
                project_id=project_id,
                workspace_id=workspace_id,
                title=title,
                description=description,
                status=TaskStatus.PENDING.value,
                priority="normal",
                plan=goals or [],
                max_steps=max_steps,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                task_config={
                    "constraints": constraints or [],
                    "verification_command": verification_command,
                },
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            logger.info(f"Created task {task.id} for agent {agent_id}")
            return task

        return self._with_db(op)

    async def start_task(
        self, task_id: int, project_root: str = ".", stream: bool = False
    ) -> Any:
        """Start executing a task."""

        def check_task(db):
            task = db.execute(
                select(Task).where(Task.id == task_id)
            ).scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found")
            if task.status != TaskStatus.PENDING.value:
                raise ValueError(
                    f"Task {task_id} cannot start from status '{task.status}'"
                )
            return task

        self._with_db(check_task)
        try:
            return await self.agent_engine.execute_task(task_id, project_root, stream)
        except Exception:

            def fail_pending(db):
                task = db.get(Task, task_id)
                if task is not None and task.status in {"pending", "running"}:
                    task.status = "failed"
                    task.error = "Task could not start; check the agent and provider configuration"
                    task.updated_at = datetime.now(timezone.utc).isoformat()
                    db.commit()

            self._with_db(fail_pending)
            raise

    async def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""

        def op(db):
            return db.execute(
                select(Task).where(Task.id == task_id)
            ).scalar_one_or_none()

        return self._with_db(op)

    async def list_tasks(
        self,
        agent_id: Optional[int] = None,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Task]:
        """List tasks with optional filtering."""

        def op(db):
            query = select(Task)

            if agent_id is not None:
                query = query.where(Task.agent_id == agent_id)
            if project_id is not None:
                query = query.where(Task.project_id == project_id)
            if status is not None:
                query = query.where(Task.status == status)

            query = query.order_by(Task.created_at.desc()).limit(limit)
            return db.execute(query).scalars().all()

        return self._with_db(op)

    async def cancel_task(self, task_id: int) -> bool:
        """Cancel a running task."""
        return await self.agent_engine.cancel_task(task_id)

    async def get_task_steps(self, task_id: int) -> List[TaskStep]:
        """Get all steps for a task."""

        def op(db):
            result = db.execute(
                select(TaskStep)
                .where(TaskStep.task_id == task_id)
                .order_by(TaskStep.step_index)
            )
            return result.scalars().all()

        return self._with_db(op)

    async def get_task_with_results(self, task_id: int) -> Dict[str, Any]:
        """Get a task with its steps and results."""

        def op(db):
            task = db.execute(
                select(Task).where(Task.id == task_id)
            ).scalar_one_or_none()
            if not task:
                return {"error": f"Task {task_id} not found"}

            steps_result = db.execute(
                select(TaskStep)
                .where(TaskStep.task_id == task_id)
                .order_by(TaskStep.step_index)
            )
            steps = steps_result.scalars().all()

            return {
                "task": {
                    "id": task.id,
                    "agent_id": task.agent_id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "plan": task.plan,
                    "result": task.result,
                    "error": task.error,
                    "max_steps": task.max_steps,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                },
                "steps": [
                    {
                        "step_index": s.step_index,
                        "kind": s.kind,
                        "content": s.content,
                        "tool_name": s.tool_name,
                        "tool_result": s.tool_result,
                        "error": s.error,
                        "created_at": s.created_at,
                    }
                    for s in steps
                ],
                "step_count": len(steps),
            }

        return self._with_db(op)

    async def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> Optional[Task]:
        """Update task properties."""

        def op(db):
            task = db.execute(
                select(Task).where(Task.id == task_id)
            ).scalar_one_or_none()
            if not task:
                return None

            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if priority is not None:
                task.priority = priority
            if max_steps is not None:
                task.max_steps = max_steps

            task.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            db.refresh(task)
            return task

        return self._with_db(op)

    async def delete_task(self, task_id: int) -> bool:
        """Delete a task and its steps."""

        def op(db):
            # Delete steps first
            db.execute(delete(TaskStep).where(TaskStep.task_id == task_id))

            task = db.execute(
                select(Task).where(Task.id == task_id)
            ).scalar_one_or_none()
            if not task:
                return False

            db.delete(task)
            db.commit()
            logger.info(f"Deleted task {task_id}")
            return True

        return self._with_db(op)


# Global task service instance
_task_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """Get the global task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
