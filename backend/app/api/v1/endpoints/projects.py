"""Project and workspace API endpoints."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as PathParam, Body

from app.core.config import settings
from app.core.security import resolve_within_root
from typing import Optional

from app.services.project_service import ProjectService
from app.services.event_bus import EventBus

router = APIRouter(tags=["Projects"])

# Dependency to get project service
def get_project_service() -> ProjectService:
    return ProjectService(EventBus())


@router.post("/", response_model=dict, summary="Create a new project")
async def create_project(
    name: str = Body(..., description="Project name"),
    description: Optional[str] = Body(None, description="Project description"),
):
    """Create a new project."""
    service = get_project_service()
    project = await service.create_project(name=name, description=description)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.get("/", response_model=dict, summary="List all projects")
async def list_projects():
    """List all projects."""
    service = get_project_service()
    projects = await service.list_projects()
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in projects
        ]
    }


@router.get("/{project_id}", response_model=dict, summary="Get a project by ID")
async def get_project(
    project_id: int = PathParam(..., description="Project ID"),
):
    """Get a project by ID."""
    service = get_project_service()
    project = await service.get_project(project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.put("/{project_id}", response_model=dict, summary="Update a project")
async def update_project(
    project_id: int = PathParam(..., description="Project ID"),
    name: Optional[str] = Body(None, description="New project name"),
    description: Optional[str] = Body(None, description="New project description"),
):
    """Update a project."""
    service = get_project_service()
    project = await service.update_project(
        project_id=project_id, name=name, description=description
    )
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.delete("/{project_id}", response_model=dict, summary="Delete a project")
async def delete_project(
    project_id: int = PathParam(..., description="Project ID"),
):
    """Delete a project."""
    service = get_project_service()
    success = await service.delete_project(project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"deleted": True, "project_id": project_id}


@router.post("/{project_id}/workspace", response_model=dict, summary="Open or initialize a project's workspace")
async def open_project_workspace(project_id: int = PathParam(..., ge=1)):
    """Create the project-scoped directory and return its root-relative path."""
    project = await get_project_service().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    try:
        root = settings.PROJECT_ROOT.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        workspace = resolve_within_root(root, str(project_id))
        workspace.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Could not initialize this project's workspace.") from exc
    return {"project_id": project_id, "name": project.name, "path": workspace.relative_to(root).as_posix()}
