"""Memory models for session, project, and preference storage."""

from sqlalchemy import String, Text, Integer, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SessionMemory(Base):
    """Memory stored for the current session - transient context, chat history, short-term reasoning."""

    __tablename__ = "session_memories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("uq_session_key", "session_id", "key", unique=True),
    )

    def __repr__(self):
        return f"<SessionMemory session={self.session_id} key={self.key}>"


class ProjectMemory(Base):
    """Memory about a specific project - understanding, conventions, important files, patterns."""

    __tablename__ = "project_memories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("uq_project_key", "project_id", "key", unique=True),
    )

    def __repr__(self):
        return f"<ProjectMemory project={self.project_id} key={self.key}>"


class LongTermPreference(Base):
    """User long-term preferences and configurations that persist across sessions."""

    __tablename__ = "long_term_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(256), nullable=False, default="default", index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g., "editor", "llm", "workflow"
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="global")  # "global", "project", "workflow"
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("uq_user_category_key", "user_id", "category", "key", unique=True),
    )

    def __repr__(self):
        return f"<LongTermPreference user={self.user_id} category={self.category} key={self.key}>"


class ContextRetrieval(Base):
    """Historical context retrievals for improving context retrieval over time."""

    __tablename__ = "context_retrievals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[dict] = mapped_column(JSON, nullable=False)
    similarity: Mapped[str] = mapped_column(String(32), nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self):
        return f"<ContextRetrieval session={self.session_id} query_hash={hash(self.query)[:8]}>"


class ProjectUnderstanding(Base):
    """Structured understanding of a project - its structure, conventions, and important elements."""

    __tablename__ = "project_understandings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    understanding: Mapped[dict] = mapped_column(JSON, nullable=False)
    last_updated: Mapped[str] = mapped_column(String(32), nullable=False)
    update_reason: Mapped[str] = mapped_column(String(256), nullable=True)

    def __repr__(self):
        return f"<ProjectUnderstanding project={self.project_id}>"


__all__ = [
    "SessionMemory",
    "ProjectMemory",
    "LongTermPreference",
    "ContextRetrieval",
    "ProjectUnderstanding",
]