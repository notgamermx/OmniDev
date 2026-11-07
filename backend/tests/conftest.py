"""Isolated databases for services that use their own session factory."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
import app.models  # Register mapped tables.
import app.models.memory
import app.models.shared_session
import app.models.conversation


@pytest.fixture
def isolated_service_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'services.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    for module in ("memory_service", "shared_session_service", "project_service", "task_service", "agent_service", "agent_engine"):
        monkeypatch.setattr(f"app.services.{module}.SessionLocal", factory)
    monkeypatch.setattr("app.api.v1.endpoints.workbench.SessionLocal", factory)
    yield
    engine.dispose()
