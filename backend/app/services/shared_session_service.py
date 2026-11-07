"""Shared session service for collaborative work."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.shared_session import SharedSession, SharedSessionMembership, WebSocketSession
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class SharedSessionService:
    """Service for managing shared sessions."""

    def __init__(self, memory_service: Optional[MemoryService] = None) -> None:
        self.memory_service = memory_service or MemoryService()

    def _with_db(self, operation):
        """Execute an operation with a database session."""
        db = SessionLocal()
        try:
            return operation(db)
        finally:
            db.close()

    # ==========================================
    # Session Management
    # ==========================================

    async def create_shared_session(
        self,
        owner_user_id: str,
        project_id: Optional[int] = None,
        session_name: str = "New Session",
        description: Optional[str] = None,
        permission: str = "read",
        expires_hours: Optional[int] = None
    ) -> SharedSession:
        """Create a new shared session."""
        session_id = f"session_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()

        expires_at = None
        if expires_hours:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()

        def op(db: Session):
            session = SharedSession(
                session_id=session_id,
                owner_user_id=owner_user_id,
                project_id=project_id,
                session_name=session_name,
                description=description,
                permission=permission,
                expires_at=expires_at,
                is_active=True,
                access_count=0,
                created_at=now,
                updated_at=now,
                shared_with=[]
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Created shared session: {session_id}")
            return session

        return self._with_db(op)

    async def get_shared_session(self, session_id: str) -> Optional[SharedSession]:
        """Get a shared session by ID."""
        def op(db: Session):
            return db.execute(
                select(SharedSession).where(
                    SharedSession.session_id == session_id,
                    SharedSession.is_active == True
                )
            ).scalar_one_or_none()
        return self._with_db(op)

    async def list_user_sessions(self, user_id: str) -> List[SharedSession]:
        """List sessions for a user (owned or shared with)."""
        def op(db: Session):
            return db.execute(
                select(SharedSession).where(
                    or_(
                        SharedSession.owner_user_id == user_id,
                        SharedSession.shared_with.contains([user_id])
                    )
                ).order_by(SharedSession.updated_at.desc())
            ).scalars().all()
        return self._with_db(op)

    async def share_session(
        self,
        session_id: str,
        shared_with: List[str],
        permission: str = "read"
    ) -> SharedSession:
        """Share a session with other users."""
        def op(db: Session):
            session = db.execute(
                select(SharedSession).where(SharedSession.session_id == session_id)
            ).scalar_one_or_none()

            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Add new users to shared_with
            existing = set(session.shared_with or [])
            new_users = [u for u in shared_with if u not in existing]
            session.shared_with = list(existing | set(shared_with))
            session.updated_at = datetime.now(timezone.utc).isoformat()

            db.commit()
            db.refresh(session)
            return session

        return self._with_db(op)

    async def unshare_session(self, session_id: str, user_id: str) -> bool:
        """Remove a user from a shared session."""
        def op(db: Session):
            session = db.execute(
                select(SharedSession).where(SharedSession.session_id == session_id)
            ).scalar_one_or_none()

            if not session:
                return False

            existing = set(session.shared_with or [])
            if user_id in existing:
                existing.remove(user_id)
                session.shared_with = list(existing)
                session.updated_at = datetime.now(timezone.utc).isoformat()
                db.commit()

            return True

        return self._with_db(op)

    async def end_shared_session(self, session_id: str) -> bool:
        """End a shared session."""
        def op(db: Session):
            session = db.execute(
                select(SharedSession).where(SharedSession.session_id == session_id)
            ).scalar_one_or_none()

            if not session:
                return False

            session.is_active = False
            session.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # Session Membership
    # ==========================================

    async def join_session(
        self,
        session_id: str,
        user_id: str,
        role: str = "viewer"
    ) -> SharedSessionMembership:
        """Join a shared session."""
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            # Check if session exists
            session = db.execute(
                select(SharedSession).where(SharedSession.session_id == session_id)
            ).scalar_one_or_none()

            if not session or not session.is_active:
                raise ValueError(f"Session {session_id} not available")

            # Check if user has access
            if session.owner_user_id != user_id and user_id not in (session.shared_with or []):
                raise ValueError("Access denied")

            # Check if already a member
            existing = db.execute(
                select(SharedSessionMembership).where(
                    SharedSessionMembership.session_id == session_id,
                    SharedSessionMembership.user_id == user_id
                )
            ).scalar_one_or_none()

            if existing:
                return existing

            # Create membership
            membership = SharedSessionMembership(
                session_id=session_id,
                user_id=user_id,
                role=role,
                joined_at=now
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)
            return membership

        return self._with_db(op)

    async def get_session_members(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all members of a session."""
        def op(db: Session):
            memberships = db.execute(
                select(SharedSessionMembership).where(
                    SharedSessionMembership.session_id == session_id
                )
            ).scalars().all()

            return [
                {
                    "user_id": m.user_id,
                    "role": m.role,
                    "joined_at": m.joined_at,
                    "activities": m.activities,
                    "last_seen": m.last_seen
                }
                for m in memberships
            ]
        return self._with_db(op)

    async def leave_session(self, session_id: str, user_id: str) -> bool:
        """Leave a session."""
        def op(db: Session):
            membership = db.execute(
                select(SharedSessionMembership).where(
                    SharedSessionMembership.session_id == session_id,
                    SharedSessionMembership.user_id == user_id
                )
            ).scalar_one_or_none()

            if not membership:
                return False

            db.delete(membership)
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # WebSocket Session Tracking
    # ==========================================

    async def create_websocket_session(
        self,
        session_id: str,
        user_id: str,
        channels: Optional[List[str]] = None
    ) -> WebSocketSession:
        """Create a WebSocket session record."""
        ws_id = f"ws_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()

        def op(db: Session):
            record = WebSocketSession(
                session_id=session_id,
                connection_id=ws_id,
                user_id=user_id,
                connected_at=now,
                last_ping=now,
                is_active=True,
                channels=channels or []
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

        return self._with_db(op)

    async def update_websocket_session(self, connection_id: str, **updates) -> Optional[WebSocketSession]:
        """Update a WebSocket session."""
        def op(db: Session):
            record = db.execute(
                select(WebSocketSession).where(WebSocketSession.connection_id == connection_id)
            ).scalar_one_or_none()

            if not record:
                return None

            for key, value in updates.items():
                setattr(record, key, value)

            db.commit()
            db.refresh(record)
            return record

        return self._with_db(op)

    async def get_active_websocket_sessions(self, session_id: str) -> List[WebSocketSession]:
        """Get all active WebSocket sessions for a session."""
        def op(db: Session):
            return db.execute(
                select(WebSocketSession).where(
                    WebSocketSession.session_id == session_id,
                    WebSocketSession.is_active == True
                )
            ).scalars().all()
        return self._with_db(op)

    async def end_websocket_session(self, connection_id: str) -> bool:
        """End a WebSocket session."""
        def op(db: Session):
            record = db.execute(
                select(WebSocketSession).where(WebSocketSession.connection_id == connection_id)
            ).scalar_one_or_none()

            if not record:
                return False

            record.is_active = False
            db.commit()
            return True

        return self._with_db(op)

    # ==========================================
    # Access Tracking
    # ==========================================

    def record_session_access(self, session_id: str, user_id: str) -> None:
        """Record a session access."""
        def op(db: Session):
            session = db.execute(
                select(SharedSession).where(SharedSession.session_id == session_id)
            ).scalar_one_or_none()

            if session:
                session.access_count += 1
                session.last_accessed = datetime.now(timezone.utc).isoformat()
                db.commit()

        self._with_db(op)


# Global singleton
_shared_session_service: Optional[SharedSessionService] = None


def get_shared_session_service() -> SharedSessionService:
    """Get the global shared session service."""
    global _shared_session_service
    if _shared_session_service is None:
        _shared_session_service = SharedSessionService()
    return _shared_session_service