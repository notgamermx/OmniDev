"""Shared session model for collaborative work."""

from sqlalchemy import String, Text, Integer, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from app.database.base import Base


class SharedSession(Base):
    """A session that can be shared between multiple users."""

    __tablename__ = "shared_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)

    # Sharing info
    owner_user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    shared_with: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # List of user IDs
    permission: Mapped[str] = mapped_column(String(32), nullable=False, default="read")  # read, write, admin

    # Session metadata
    project_id: Mapped[int] = mapped_column(Integer, nullable=True)
    session_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Expiration
    expires_at: Mapped[str] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Access log
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed: Mapped[str] = mapped_column(String(32), nullable=True)

    # Timestamps
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self):
        return f"<SharedSession {self.session_id} by {self.owner_user_id}>"


class SharedSessionMembership(Base):
    """Membership record for a user's participation in a shared session."""

    __tablename__ = "shared_session_memberships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # Role and permissions
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")  # viewer, contributor, admin
    joined_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_seen: Mapped[str] = mapped_column(String(32), nullable=True)

    # Activity tracking
    activities: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Number of interactions

    __table_args__ = (
        Index("uq_session_user", "session_id", "user_id", unique=True),
    )

    def __repr__(self):
        return f"<SessionMembership {self.session_id} user={self.user_id} role={self.role}>"


class WebSocketSession(Base):
    """Active WebSocket connection tracking for real-time updates."""

    __tablename__ = "websocket_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    connection_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)

    user_id: Mapped[str] = mapped_column(String(256), nullable=False)

    # Connection info
    connected_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_ping: Mapped[str] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Channels this connection is subscribed to
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    def __repr__(self):
        return f"<WebSocketSession {self.connection_id} user={self.user_id}>"


__all__ = ["SharedSession", "SharedSessionMembership", "WebSocketSession"]