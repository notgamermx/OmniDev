"""Project service for managing projects and workspaces."""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from sqlalchemy import select, delete

from app.database.session import SessionLocal
from app.models.metadata import Project, Workspace
from app.core.security import resolve_within_root
from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects and workspaces."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus or EventBus()

    def _with_db(self, operation):
        """Execute an operation with a database session."""
        db = SessionLocal()
        try:
            return operation(db)
        finally:
            db.close()

    async def create_project(self, name: str, description: Optional[str] = None) -> Project:
        """Create a new project."""
        def op(db):
            project = Project(
                name=name,
                description=description,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            logger.info(f"Created project: {project.id} - {project.name}")
            return project

        project = self._with_db(op)

        # Publish project created event
        await self.event_bus.publish("project.created", {
            "project_id": project.id,
            "project_name": project.name,
        })
        return project

    async def get_project(self, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        def op(db):
            return db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
        return self._with_db(op)

    async def list_projects(self) -> List[Project]:
        """List all projects."""
        def op(db):
            return db.execute(select(Project).order_by(Project.name)).scalars().all()
        return self._with_db(op)

    async def update_project(self, project_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Project]:
        """Update a project."""
        def op(db):
            project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
            if not project:
                return None
            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            project.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            db.refresh(project)
            return project
        return self._with_db(op)

    async def delete_project(self, project_id: int) -> bool:
        """Delete a project and its workspaces."""
        def op(db):
            # Delete associated workspaces first
            db.execute(delete(Workspace).where(Workspace.project_id == project_id))
            result = db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                return False
            db.delete(project)
            db.commit()
            logger.info(f"Deleted project: {project_id}")
            return True
        return self._with_db(op)

    async def create_workspace(
        self,
        project_id: int,
        name: str,
        path: str,
    ) -> Workspace:
        """Create a new workspace within a project."""
        # Verify project exists
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} does not exist")

        def op(db):
            workspace = Workspace(
                project_id=project_id,
                name=name,
                path=path,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(workspace)
            db.commit()
            db.refresh(workspace)
            logger.info(f"Created workspace: {workspace.id} - {name}")
            return workspace

        workspace = self._with_db(op)

        # Publish workspace created event
        await self.event_bus.publish("workspace.created", {
            "workspace_id": workspace.id,
            "project_id": project_id,
            "workspace_name": name,
        })
        return workspace

    async def get_workspace(self, workspace_id: int) -> Optional[Workspace]:
        """Get a workspace by ID."""
        def op(db):
            return db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
        return self._with_db(op)

    async def list_workspaces(self, project_id: Optional[int] = None) -> List[Workspace]:
        """List workspaces, optionally filtered by project."""
        def op(db):
            query = select(Workspace).order_by(Workspace.name)
            if project_id is not None:
                query = query.where(Workspace.project_id == project_id)
            return db.execute(query).scalars().all()
        return self._with_db(op)

    async def update_workspace(
        self,
        workspace_id: int,
        name: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Optional[Workspace]:
        """Update a workspace."""
        def op(db):
            workspace = db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
            if not workspace:
                return None
            if name is not None:
                workspace.name = name
            if path is not None:
                # Validate path stays within root
                try:
                    resolve_within_root(Path.cwd(), path)
                    workspace.path = path
                except ValueError:
                    logger.warning(f"Path outside root rejected for workspace {workspace_id}")
            workspace.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            db.refresh(workspace)
            return workspace
        return self._with_db(op)

    async def delete_workspace(self, workspace_id: int) -> bool:
        """Delete a workspace."""
        def op(db):
            workspace = db.execute(select(Workspace).where(Workspace.id == workspace_id)).scalar_one_or_none()
            if not workspace:
                return False
            db.delete(workspace)
            db.commit()
            logger.info(f"Deleted workspace: {workspace_id}")
            return True
        return self._with_db(op)