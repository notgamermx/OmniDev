"""Web dashboard API endpoints."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Body, HTTPException

from app.services.memory_service import MemoryService, get_memory_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])


# ==========================================
# Dashboard Session Management (for web UI)
# ==========================================

@router.post("/session", summary="Create dashboard session")
async def create_dashboard_session(
    user_id: str = Body("anonymous", description="User identifier"),
    project_id: Optional[int] = Body(None, description="Active project ID")
):
    """Create a dashboard session for collaborative viewing."""
    session_id = f"dash_{uuid.uuid4().hex[:12]}"

    memory_service = get_memory_service()

    # Store session info
    await memory_service.set_session_memory(
        session_id,
        data={
            "user_id": user_id,
            "project_id": project_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True
        }
    )

    return {
        "session_id": session_id,
        "user_id": user_id,
        "project_id": project_id,
        "status": "active"
    }


@router.get("/session/{session_id}", summary="Get dashboard session")
async def get_dashboard_session(session_id: str):
    """Get dashboard session details."""
    memory_service = get_memory_service()
    mem = await memory_service.get_session_memory(session_id)

    if not mem:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "data": mem.data
    }


@router.delete("/session/{session_id}", summary="End dashboard session")
async def end_dashboard_session(session_id: str):
    """End a dashboard session."""
    memory_service = get_memory_service()
    await memory_service.delete_session_memory(session_id)
    return {"ended": True, "session_id": session_id}


# ==========================================
# Project Views
# ==========================================

@router.get("/projects", summary="List dashboard projects")
async def list_dashboard_projects():
    """List all projects for the dashboard."""
    # This would query projects - using memory service for demo
    return {
        "projects": [
            {"id": 1, "name": "Sample Project", "memories_count": 5},
            {"id": 2, "name": "Another Project", "memories_count": 2}
        ]
    }


@router.get("/project/{project_id}/snapshot", summary="Get project snapshot")
async def get_project_snapshot(project_id: int):
    """Get a dashboard-friendly snapshot of a project."""
    memory_service = get_memory_service()

    # Get all project memories
    memories = await memory_service.list_project_memories(project_id)

    # Get understanding
    understanding = await memory_service.get_project_understanding(project_id)

    return {
        "project_id": project_id,
        "memories": [
            {
                "key": m.key,
                "value": m.value,
                "importance": m.importance
            }
            for m in memories
        ],
        "understanding": understanding.understanding if understanding else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==========================================
# Real-time Status
# ==========================================

@router.get("/status", summary="Get dashboard status")
async def get_dashboard_status():
    """Get current dashboard system status."""
    return {
        "api_available": True,
        "active_sessions": 0,
        "projects_count": 0,
        "last_update": datetime.now(timezone.utc).isoformat()
    }