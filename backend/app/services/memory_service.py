"""Memory service for session, project, and preference storage."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json
import uuid

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.memory import (
    SessionMemory,
    ProjectMemory,
    LongTermPreference,
    ContextRetrieval,
    ProjectUnderstanding,
)
logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing session, project, and preference memory."""

    def __init__(self) -> None:
        self._session_id: Optional[str] = None

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for memory operations."""
        self._session_id = session_id

    def get_session_id(self) -> str:
        """Get or create session ID."""
        if self._session_id is None:
            self._session_id = str(uuid.uuid4())
        return self._session_id

    # ==========================================
    # SESSION MEMORY (transient, per-session)
    # ==========================================

    def _with_db(self, operation):
        """Execute an operation with a database session."""
        db = SessionLocal()
        try:
            return operation(db)
        finally:
            db.close()

    async def set_session_memory(
        self,
        key: str,
        value: Optional[str] = None,
        data: Optional[dict] = None,
        session_id: Optional[str] = None
    ) -> SessionMemory:
        """Set a session-level memory value."""
        sid = session_id or self.get_session_id()
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            # Check if exists
            existing = db.execute(
                select(SessionMemory).where(
                    SessionMemory.session_id == sid,
                    SessionMemory.key == key
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = value
                existing.data = data
                existing.updated_at = now
                db.commit()
                db.refresh(existing)
                return existing

            memory = SessionMemory(
                session_id=sid,
                key=key,
                value=value,
                data=data,
                created_at=now,
                updated_at=now
            )
            db.add(memory)
            db.commit()
            db.refresh(memory)
            return memory

        return self._with_db(op)

    async def get_session_memory(
        self,
        key: str,
        session_id: Optional[str] = None
    ) -> Optional[SessionMemory]:
        """Get a session-level memory value."""
        sid = session_id or self.get_session_id()

        def op(db: Session):
            return db.execute(
                select(SessionMemory).where(
                    SessionMemory.session_id == sid,
                    SessionMemory.key == key
                )
            ).scalar_one_or_none()

        return self._with_db(op)

    async def list_session_memories(
        self,
        session_id: Optional[str] = None
    ) -> List[SessionMemory]:
        """List all memories for a session."""
        sid = session_id or self.get_session_id()

        def op(db: Session):
            return db.execute(
                select(SessionMemory).where(SessionMemory.session_id == sid)
            ).scalars().all()

        return self._with_db(op)

    async def delete_session_memory(
        self,
        key: str,
        session_id: Optional[str] = None
    ) -> bool:
        """Delete a session-level memory."""
        sid = session_id or self.get_session_id()

        def op(db: Session):
            memory = db.execute(
                select(SessionMemory).where(
                    SessionMemory.session_id == sid,
                    SessionMemory.key == key
                )
            ).scalar_one_or_none()

            if not memory:
                return False

            db.delete(memory)
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # PROJECT MEMORY
    # ==========================================

    async def set_project_memory(
        self,
        project_id: int,
        key: str,
        value: Optional[str] = None,
        data: Optional[dict] = None,
        importance: int = 0
    ) -> ProjectMemory:
        """Set a project-level memory value."""
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            existing = db.execute(
                select(ProjectMemory).where(
                    ProjectMemory.project_id == project_id,
                    ProjectMemory.key == key
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = value
                existing.data = data
                existing.importance = importance
                existing.updated_at = now
                db.commit()
                db.refresh(existing)
                return existing

            memory = ProjectMemory(
                project_id=project_id,
                key=key,
                value=value,
                data=data,
                importance=importance,
                created_at=now,
                updated_at=now
            )
            db.add(memory)
            db.commit()
            db.refresh(memory)
            return memory

        return self._with_db(op)

    async def get_project_memory(
        self,
        project_id: int,
        key: str
    ) -> Optional[ProjectMemory]:
        """Get a project-level memory value."""
        def op(db: Session):
            return db.execute(
                select(ProjectMemory).where(
                    ProjectMemory.project_id == project_id,
                    ProjectMemory.key == key
                )
            ).scalar_one_or_none()

        return self._with_db(op)

    async def get_project_memories_by_prefix(
        self,
        project_id: int,
        prefix: str
    ) -> List[ProjectMemory]:
        """Get all project memories with keys starting with prefix."""
        def op(db: Session):
            return db.execute(
                select(ProjectMemory).where(
                    ProjectMemory.project_id == project_id,
                    ProjectMemory.key.like(f"{prefix}%")
                ).order_by(desc(ProjectMemory.importance))
            ).scalars().all()

        return self._with_db(op)

    async def list_project_memories(
        self,
        project_id: int
    ) -> List[ProjectMemory]:
        """List all project memories."""
        def op(db: Session):
            return db.execute(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id)
            ).scalars().all()

        return self._with_db(op)

    async def delete_project_memory(
        self,
        project_id: int,
        key: str
    ) -> bool:
        """Delete a project-level memory."""
        def op(db: Session):
            memory = db.execute(
                select(ProjectMemory).where(
                    ProjectMemory.project_id == project_id,
                    ProjectMemory.key == key
                )
            ).scalar_one_or_none()

            if not memory:
                return False

            db.delete(memory)
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # LONG-TERM PREFERENCES
    # ==========================================

    async def set_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Optional[str] = None,
        data: Optional[dict] = None,
        scope: str = "global"
    ) -> LongTermPreference:
        """Set a long-term preference."""
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            existing = db.execute(
                select(LongTermPreference).where(
                    LongTermPreference.user_id == user_id,
                    LongTermPreference.category == category,
                    LongTermPreference.key == key
                )
            ).scalar_one_or_none()

            if existing:
                existing.value = value
                existing.data = data
                existing.scope = scope
                existing.updated_at = now
                db.commit()
                db.refresh(existing)
                return existing

            pref = LongTermPreference(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                data=data,
                scope=scope,
                created_at=now,
                updated_at=now
            )
            db.add(pref)
            db.commit()
            db.refresh(pref)
            return pref

        return self._with_db(op)

    async def get_preference(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> Optional[LongTermPreference]:
        """Get a long-term preference."""
        def op(db: Session):
            return db.execute(
                select(LongTermPreference).where(
                    LongTermPreference.user_id == user_id,
                    LongTermPreference.category == category,
                    LongTermPreference.key == key
                )
            ).scalar_one_or_none()

        return self._with_db(op)

    async def list_preferences(
        self,
        user_id: str,
        category: Optional[str] = None,
        scope: Optional[str] = None
    ) -> List[LongTermPreference]:
        """List preferences with optional filtering."""
        def op(db: Session):
            query = select(LongTermPreference).where(LongTermPreference.user_id == user_id)
            if category:
                query = query.where(LongTermPreference.category == category)
            if scope:
                query = query.where(LongTermPreference.scope == scope)
            return db.execute(query.order_by(LongTermPreference.category, LongTermPreference.key)).scalars().all()

        return self._with_db(op)

    async def delete_preference(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> bool:
        """Delete a preference."""
        def op(db: Session):
            pref = db.execute(
                select(LongTermPreference).where(
                    LongTermPreference.user_id == user_id,
                    LongTermPreference.category == category,
                    LongTermPreference.key == key
                )
            ).scalar_one_or_none()

            if not pref:
                return False

            db.delete(pref)
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # CONTEXT RETRIEVAL
    # ==========================================

    async def record_context_retrieval(
        self,
        query: str,
        results: dict,
        similarity: Optional[float] = None,
        session_id: Optional[str] = None
    ) -> ContextRetrieval:
        """Record a context retrieval for future learning."""
        sid = session_id or self.get_session_id()
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            record = ContextRetrieval(
                session_id=sid,
                query=query,
                results=results,
                similarity=str(similarity) if similarity is not None else None,
                created_at=now
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

        return self._with_db(op)

    async def get_recent_context_retrievals(
        self,
        session_id: Optional[str] = None,
        limit: int = 10,
        used_only: bool = False
    ) -> List[ContextRetrieval]:
        """Get recent context retrievals."""
        sid = session_id or self.get_session_id()

        def op(db: Session):
            query = select(ContextRetrieval).where(ContextRetrieval.session_id == sid)
            if used_only:
                query = query.where(ContextRetrieval.used == True)
            return db.execute(query.order_by(desc(ContextRetrieval.created_at)).limit(limit)).scalars().all()

        return self._with_db(op)

    async def mark_retrieval_as_used(self, retrieval_id: int) -> bool:
        """Mark a retrieval as having been used."""
        def op(db: Session):
            record = db.execute(select(ContextRetrieval).where(ContextRetrieval.id == retrieval_id)).scalar_one_or_none()
            if not record:
                return False
            record.used = True
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # PROJECT UNDERSTANDING
    # ==========================================

    async def set_project_understanding(
        self,
        project_id: int,
        understanding: dict,
        update_reason: Optional[str] = None
    ) -> ProjectUnderstanding:
        """Set the structured understanding of a project."""
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            existing = db.execute(
                select(ProjectUnderstanding).where(ProjectUnderstanding.project_id == project_id)
            ).scalar_one_or_none()

            if existing:
                existing.understanding = understanding
                existing.last_updated = now
                existing.update_reason = update_reason
                db.commit()
                db.refresh(existing)
                return existing

            pu = ProjectUnderstanding(
                project_id=project_id,
                understanding=understanding,
                last_updated=now,
                update_reason=update_reason
            )
            db.add(pu)
            db.commit()
            db.refresh(pu)
            return pu

        return self._with_db(op)

    async def get_project_understanding(
        self,
        project_id: int
    ) -> Optional[ProjectUnderstanding]:
        """Get the structured understanding of a project."""
        def op(db: Session):
            return db.execute(
                select(ProjectUnderstanding).where(ProjectUnderstanding.project_id == project_id)
            ).scalar_one_or_none()

        return self._with_db(op)

    async def update_project_understanding(
        self,
        project_id: int,
        updates: dict,
        update_reason: str
    ) -> Optional[ProjectUnderstanding]:
        """Update specific aspects of project understanding."""
        def op(db: Session):
            pu = db.execute(
                select(ProjectUnderstanding).where(ProjectUnderstanding.project_id == project_id)
            ).scalar_one_or_none()

            if not pu:
                return None

            # Merge updates into existing understanding
            # Create a new dict to ensure SQLAlchemy detects the change
            current = pu.understanding if isinstance(pu.understanding, dict) else {}
            pu.understanding = {**current, **updates}

            pu.last_updated = datetime.now(timezone.utc).isoformat()
            # Append to update reason
            if pu.update_reason:
                pu.update_reason = f"{pu.update_reason}; {update_reason}"
            else:
                pu.update_reason = update_reason

            db.commit()
            db.refresh(pu)
            return pu

        return self._with_db(op)

    # ==========================================
    # UTILITY: AI-driven memory operations
    # ==========================================

    async def recall_project_context(
        self,
        project_id: int,
        query: str,
        max_items: int = 10
    ) -> Dict[str, Any]:
        """
        AI-powered context recall for a project.
        Uses similarity matching and importance ranking.
        """
        memories = await self.list_project_memories(project_id)

        # Simple keyword-based matching
        query_lower = query.lower()
        scored = []

        for mem in memories:
            score = 0
            if mem.key and query_lower in mem.key.lower():
                score += 2
            if mem.data:
                data_str = json.dumps(mem.data).lower()
                if query_lower in data_str:
                    score += 1
            if mem.importance:
                score += mem.importance * 0.5
            if mem.value:
                value_lower = mem.value.lower() if isinstance(mem.value, str) else ""
                if query_lower in value_lower:
                    score += 1

            if score > 0:
                scored.append((score, mem))

        # Sort by score and return top items
        scored.sort(key=lambda x: x[0], reverse=True)
        top_memories = [mem for _, mem in scored[:max_items]]

        return {
            "project_id": project_id,
            "query": query,
            "results": [
                {
                    "key": m.key,
                    "value": m.value,
                    "data": m.data,
                    "importance": m.importance,
                }
                for m in top_memories
            ],
            "count": len(top_memories)
        }


# Global singleton
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service