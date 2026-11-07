"""Workspace API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Path as PathParam, Body

from app.services.project_service import ProjectService
from app.services.event_bus import EventBus

router = APIRouter(tags=["Workspaces"])


def get_project_service() -> ProjectService:
    return ProjectService(EventBus())


@router.post("/", response_model=dict, summary="Create a new workspace")
async def create_workspace(
    project_id: int = Body(..., description="Project ID"),
    name: str = Body(..., description="Workspace name"),
    path: str = Body(..., description="Workspace path"),
):
    """Create a new workspace within a project."""
    service = get_project_service()
    workspace = await service.create_workspace(
        project_id=project_id, name=name, path=path
    )
    return {
        "id": workspace.id,
        "project_id": workspace.project_id,
        "name": workspace.name,
        "path": workspace.path,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
    }


@router.get("/", response_model=dict, summary="List all workspaces")
async def list_workspaces(
    project_id: Optional[int] = None,
):
    """List workspaces, optionally filtered by project."""
    service = get_project_service()
    workspaces = await service.list_workspaces(project_id=project_id)
    return {
        "workspaces": [
            {
                "id": w.id,
                "project_id": w.project_id,
                "name": w.name,
                "path": w.path,
                "created_at": w.created_at,
                "updated_at": w.updated_at,
            }
            for w in workspaces
        ]
    }


@router.get("/{workspace_id}", response_model=dict, summary="Get a workspace by ID")
async def get_workspace(
    workspace_id: int = PathParam(..., description="Workspace ID"),
):
    """Get a workspace by ID."""
    service = get_project_service()
    workspace = await service.get_workspace(workspace_id=workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return {
        "id": workspace.id,
        "project_id": workspace.project_id,
        "name": workspace.name,
        "path": workspace.path,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
    }


@router.put("/{workspace_id}", response_model=dict, summary="Update a workspace")
async def update_workspace(
    workspace_id: int = PathParam(..., description="Workspace ID"),
    name: Optional[str] = Body(None, description="New workspace name"),
    path: Optional[str] = Body(None, description="New workspace path"),
):
    """Update a workspace."""
    service = get_project_service()
    workspace = await service.update_workspace(
        workspace_id=workspace_id, name=name, path=path
    )
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return {
        "id": workspace.id,
        "project_id": workspace.project_id,
        "name": workspace.name,
        "path": workspace.path,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
    }


@router.delete("/{workspace_id}", response_model=dict, summary="Delete a workspace")
async def delete_workspace(
    workspace_id: int = PathParam(..., description="Workspace ID"),
):
    """Delete a workspace."""
    service = get_project_service()
    success = await service.delete_workspace(workspace_id=workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return {"deleted": True, "workspace_id": workspace_id}