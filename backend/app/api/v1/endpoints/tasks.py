"""Task API endpoints for agent execution."""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Response
from fastapi.responses import StreamingResponse

from app.services.task_service import TaskService, get_task_service as _get_task_service
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tasks"])


def get_task_service() -> TaskService:
    return _get_task_service()


# Helper function for streaming
async def stream_task_execution(
    task_id: int, project_root: str
) -> AsyncIterator[Dict[str, Any]]:
    """Generator for streaming task execution updates."""
    service = get_task_service()

    try:
        yield {
            "type": "status",
            "message": "Starting task execution",
            "task_id": task_id,
        }

        # Get initial task info
        task = await service.get_task(task_id)
        if not task:
            yield {"type": "error", "message": f"Task {task_id} not found"}
            return

        yield {
            "type": "task_started",
            "task": {"id": task.id, "title": task.title, "agent_id": task.agent_id},
        }

        # Execute with streaming
        from app.api.v1.endpoints.workbench import project_path

        task_result = await service.start_task(
            task_id, str(project_path(project_root)), stream=True
        )

        async for event in task_result:
            yield event

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        yield {"type": "error", "message": str(e)}


@router.post("/", response_model=dict, summary="Create a new task")
async def create_task(
    agent_id: int = Body(..., description="Agent ID to run the task"),
    title: str = Body(..., description="Task title"),
    description: Optional[str] = Body(None, description="Task description"),
    project_id: Optional[int] = Body(None, description="Project ID (optional)"),
    workspace_id: Optional[int] = Body(None, description="Workspace ID (optional)"),
    max_steps: int = Body(25, ge=1, le=200, description="Maximum execution steps"),
    goals: Optional[List[str]] = Body(None, description="Task goals/planner steps"),
    constraints: Optional[List[str]] = Body(None, description="Task constraints"),
    verification_command: Optional[str] = Body(None, max_length=10000),
):
    """Create a new task for an agent."""
    service = get_task_service()

    try:
        task = await service.create_task(
            agent_id=agent_id,
            title=title,
            description=description,
            project_id=project_id,
            workspace_id=workspace_id,
            max_steps=max_steps,
            goals=goals,
            constraints=constraints,
            verification_command=verification_command,
        )
        return {
            "id": task.id,
            "agent_id": task.agent_id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "plan": task.plan,
            "metadata": task.task_config,
            "max_steps": task.max_steps,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{task_id}/execute", response_model=dict, summary="Execute a task synchronously"
)
async def execute_task_sync(
    task_id: int = Path(..., description="Task ID"),
    project_root: str = Body(".", embed=True, description="Project root directory"),
):
    """Execute a task synchronously and wait for completion."""
    service = get_task_service()
    from app.api.v1.endpoints.workbench import project_path

    project_root = str(project_path(project_root))

    try:
        task = await service.start_task(task_id, project_root, stream=False)
        steps = await service.get_task_steps(task_id)

        return {
            "task_id": task.id,
            "status": task.status,
            "result": task.result,
            "error": task.error,
            "steps": [
                {
                    "step_index": s.step_index,
                    "kind": s.kind,
                    "content": s.content[:500] + "..."
                    if len(s.content) > 500
                    else s.content,
                    "tool_name": s.tool_name,
                    "created_at": s.created_at,
                }
                for s in steps
            ],
            "step_count": len(steps),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Task {task_id} execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{task_id}/execute/stream",
    response_class=StreamingResponse,
    summary="Execute a task with streaming",
)
async def execute_task_stream(
    task_id: int = Path(..., description="Task ID"),
    project_root: str = Body(".", embed=True, description="Project root directory"),
):
    """Execute a task with streaming updates."""
    service = get_task_service()

    try:
        task = await service.get_task(task_id)
        if not task:
            return Response(
                content=json.dumps({"error": "Task not found"}),
                media_type="application/json",
                status_code=404,
            )

        generator = stream_task_execution(task_id, project_root)

        async def event_stream():
            async for event in generator:
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=500,
        )


@router.get("/", response_model=dict, summary="List tasks")
async def list_tasks(
    agent_id: Optional[int] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
):
    """List tasks with optional filtering."""
    service = get_task_service()
    tasks = await service.list_tasks(
        agent_id=agent_id, project_id=project_id, status=status, limit=limit
    )

    return {
        "tasks": [
            {
                "id": t.id,
                "agent_id": t.agent_id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "result": t.result[:100] + "..."
                if t.result and len(t.result) > 100
                else t.result,
                "error": t.error,
                "step_count": t.step_count,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


@router.get("/{task_id}", response_model=dict, summary="Get a task by ID")
async def get_task(task_id: int = Path(..., description="Task ID")):
    """Get a task with its full execution history."""
    service = get_task_service()
    result = await service.get_task_with_results(task_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{task_id}/steps", response_model=dict, summary="Get task steps")
async def get_task_steps(task_id: int = Path(..., description="Task ID")):
    """Get all steps for a task."""
    service = get_task_service()
    steps = await service.get_task_steps(task_id)

    return {
        "task_id": task_id,
        "steps": [
            {
                "step_index": s.step_index,
                "kind": s.kind,
                "content": s.content,
                "tool_name": s.tool_name,
                "tool_args": s.tool_args,
                "tool_result": s.tool_result,
                "error": s.error,
                "created_at": s.created_at,
            }
            for s in steps
        ],
        "count": len(steps),
    }


@router.delete("/{task_id}", response_model=dict, summary="Cancel a task")
async def cancel_task(task_id: int = Path(..., description="Task ID")):
    """Cancel a running task or mark it as cancelled."""
    service = get_task_service()
    success = await service.cancel_task(task_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found or already completed/cancelled",
        )

    worker = workers.get(task_id)
    if worker is not None:
        worker.cancel()
    return {"cancelled": True, "task_id": task_id}


@router.delete("/", response_model=dict, summary="Delete a task")
async def delete_task(task_id: int = Body(..., description="Task ID to delete")):
    """Delete a task and all its steps."""
    service = get_task_service()
    success = await service.delete_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"deleted": True, "task_id": task_id}


class TaskResults:
    """Helper class for generating task result summaries."""

    @staticmethod
    def summarize_steps(steps: list) -> str:
        """Generate a summary from execution steps."""
        thoughts = [s for s in steps if s.kind == "thought"]
        actions = [s for s in steps if s.kind == "observation" and s.tool_name]
        errors = [s for s in steps if s.error]

        summary = f"Executed {len(steps)} steps: "
        summary += f"{len(thoughts)} reasoning steps, "
        summary += f"{len(actions)} tool actions, "
        if errors:
            summary += f"{len(errors)} errors"
        else:
            summary += "no errors"

        return summary


# Retain workers until completion and cancel them on application shutdown.
import asyncio

workers: dict[int, asyncio.Task] = {}


@router.post("/{task_id}/run", summary="Start a task in the background")
async def run_task(task_id: int, project_root: str = Body(".", embed=True)):
    from app.api.v1.endpoints.workbench import project_path

    service = get_task_service()
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != "pending" or task_id in workers:
        raise HTTPException(409, "Task has already started")
    path = str(project_path(project_root))

    async def run():
        try:
            await service.start_task(task_id, path)
        except Exception:
            logger.exception("Background task %s failed", task_id)
        finally:
            workers.pop(task_id, None)

    workers[task_id] = asyncio.create_task(run())
    return {"task_id": task_id, "status": "queued"}
