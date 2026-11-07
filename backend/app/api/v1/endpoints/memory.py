"""Memory API endpoints for session, project, and preference storage."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException

from app.services.memory_service import MemoryService, get_memory_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Memory"])


@router.post("/session", summary="Set session memory")
async def set_session_memory(
    key: str = Body(..., description="Memory key"),
    value: Optional[str] = Body(None, description="Memory value"),
    data: Optional[dict] = Body(None, description="Memory data (JSON)"),
    session_id: Optional[str] = Body(None, description="Session ID (optional)")
):
    """Set a session-level memory value."""
    service = get_memory_service()

    try:
        memory = await service.set_session_memory(
            key=key,
            value=value,
            data=data,
            session_id=session_id
        )
        return {
            "id": memory.id,
            "session_id": memory.session_id,
            "key": memory.key,
            "value": memory.value,
            "data": memory.data,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at
        }
    except Exception as e:
        logger.error(f"Failed to set session memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{key}", summary="Get session memory")
async def get_session_memory(key: str, session_id: Optional[str] = None):
    """Get a session-level memory value."""
    service = get_memory_service()

    memory = await service.get_session_memory(key, session_id)
    if not memory:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found")

    return {
        "key": memory.key,
        "value": memory.value,
        "data": memory.data
    }


@router.get("/session", summary="List session memories")
async def list_session_memories():
    """List all session memories."""
    service = get_memory_service()

    memories = await service.list_session_memories()
    return {
        "memories": [
            {
                "key": m.key,
                "value": m.value,
                "data": m.data
            }
            for m in memories
        ],
        "count": len(memories)
    }


@router.delete("/session/{key}", summary="Delete session memory")
async def delete_session_memory(key: str):
    """Delete a session-level memory."""
    service = get_memory_service()

    success = await service.delete_session_memory(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found")

    return {"deleted": True, "key": key}


# ==========================================
# PROJECT MEMORY
# ==========================================

@router.post("/project/{project_id}", summary="Set project memory")
async def set_project_memory(
    project_id: int,
    key: str = Body(..., description="Memory key"),
    value: Optional[str] = Body(None, description="Memory value"),
    data: Optional[dict] = Body(None, description="Memory data (JSON)"),
    importance: int = Body(0, description="Importance level (0-100)")
):
    """Set a project-level memory value."""
    service = get_memory_service()

    try:
        memory = await service.set_project_memory(
            project_id=project_id,
            key=key,
            value=value,
            data=data,
            importance=importance
        )
        return {
            "id": memory.id,
            "project_id": memory.project_id,
            "key": memory.key,
            "value": memory.value,
            "data": memory.data,
            "importance": memory.importance
        }
    except Exception as e:
        logger.error(f"Failed to set project memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/{key}", summary="Get project memory")
async def get_project_memory(project_id: int, key: str):
    """Get a project-level memory value."""
    service = get_memory_service()

    memory = await service.get_project_memory(project_id, key)
    if not memory:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found for project {project_id}")

    return {
        "key": memory.key,
        "value": memory.value,
        "data": memory.data,
        "importance": memory.importance
    }


@router.post("/project/{project_id}/recall", summary="Recall project context")
async def recall_project_context(
    project_id: int,
    query: str = Body(..., description="Query string"),
    max_items: int = Body(10, description="Maximum items to return")
):
    """AI-powered context recall for a project."""
    service = get_memory_service()

    result = await service.recall_project_context(project_id, query, max_items)
    return result


@router.get("/project/{project_id}", summary="List project memories")
async def list_project_memories(project_id: int):
    """List all project memories."""
    service = get_memory_service()

    memories = await service.list_project_memories(project_id)
    return {
        "project_id": project_id,
        "memories": [
            {
                "key": m.key,
                "value": m.value,
                "data": m.data,
                "importance": m.importance
            }
            for m in memories
        ],
        "count": len(memories)
    }


@router.delete("/project/{project_id}/{key}", summary="Delete project memory")
async def delete_project_memory(project_id: int, key: str):
    """Delete a project-level memory."""
    service = get_memory_service()

    success = await service.delete_project_memory(project_id, key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory '{key}' not found for project {project_id}")

    return {"deleted": True, "project_id": project_id, "key": key}


# ==========================================
# LONG-TERM PREFERENCES
# ==========================================

@router.post("/preference", summary="Set a long-term preference")
async def set_preference(
    user_id: str = Body("default", description="User ID"),
    category: str = Body(..., description="Preference category"),
    key: str = Body(..., description="Preference key"),
    value: Optional[str] = Body(None, description="Preference value"),
    data: Optional[dict] = Body(None, description="Preference data (JSON)"),
    scope: str = Body("global", description="Scope: global, project, or workflow")
):
    """Set a long-term user preference."""
    service = get_memory_service()

    try:
        pref = await service.set_preference(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            data=data,
            scope=scope
        )
        return {
            "id": pref.id,
            "user_id": pref.user_id,
            "category": pref.category,
            "key": pref.key,
            "value": pref.value,
            "data": pref.data,
            "scope": pref.scope
        }
    except Exception as e:
        logger.error(f"Failed to set preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preference/{category}/{key}", summary="Get a long-term preference")
async def get_preference(
    category: str,
    key: str,
    user_id: str = "default"
):
    """Get a long-term user preference."""
    service = get_memory_service()

    pref = await service.get_preference(user_id, category, key)
    if not pref:
        raise HTTPException(status_code=404, detail=f"Preference '{category}:{key}' not found")

    return {
        "user_id": pref.user_id,
        "category": pref.category,
        "key": pref.key,
        "value": pref.value,
        "data": pref.data,
        "scope": pref.scope
    }


@router.get("/preference", summary="List long-term preferences")
async def list_preferences(
    category: Optional[str] = None,
    scope: Optional[str] = None,
    user_id: str = "default"
):
    """List preferences with optional filtering."""
    service = get_memory_service()

    prefs = await service.list_preferences(user_id, category, scope)
    return {
        "user_id": user_id,
        "preferences": [
            {
                "category": p.category,
                "key": p.key,
                "value": p.value,
                "data": p.data,
                "scope": p.scope
            }
            for p in prefs
        ],
        "count": len(prefs)
    }


@router.delete("/preference/{category}/{key}", summary="Delete a preference")
async def delete_preference(category: str, key: str, user_id: str = "default"):
    """Delete a long-term preference."""
    service = get_memory_service()

    success = await service.delete_preference(user_id, category, key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Preference '{category}:{key}' not found")

    return {"deleted": True, "category": category, "key": key}


# ==========================================
# PROJECT UNDERSTANDING
# ==========================================

@router.get("/understanding/{project_id}", summary="Get project understanding")
async def get_project_understanding(project_id: int):
    """Get the structured understanding of a project."""
    service = get_memory_service()

    understanding = await service.get_project_understanding(project_id)
    if not understanding:
        raise HTTPException(status_code=404, detail=f"No understanding found for project {project_id}")

    return {
        "project_id": understanding.project_id,
        "understanding": understanding.understanding,
        "last_updated": understanding.last_updated,
        "update_reason": understanding.update_reason
    }


@router.post("/understanding/{project_id}", summary="Set project understanding")
async def set_project_understanding(
    project_id: int,
    understanding: dict = Body(..., description="Structured project understanding"),
    update_reason: Optional[str] = Body(None, description="Reason for update")
):
    """Set the structured understanding of a project."""
    service = get_memory_service()

    pu = await service.set_project_understanding(project_id, understanding, update_reason)
    return {
        "project_id": pu.project_id,
        "understanding": pu.understanding,
        "last_updated": pu.last_updated,
        "update_reason": pu.update_reason
    }


@router.post("/understanding/{project_id}/update", summary="Update project understanding")
async def update_project_understanding(
    project_id: int,
    updates: dict = Body(..., description="Updates to merge into understanding"),
    update_reason: str = Body(..., description="Reason for update")
):
    """Update specific aspects of project understanding."""
    service = get_memory_service()

    pu = await service.update_project_understanding(project_id, updates, update_reason)
    if not pu:
        raise HTTPException(status_code=404, detail=f"No understanding found for project {project_id}")

    return {
        "project_id": pu.project_id,
        "understanding": pu.understanding,
        "last_updated": pu.last_updated,
        "update_reason": pu.update_reason
    }