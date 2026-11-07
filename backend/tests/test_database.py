from sqlalchemy import create_engine, inspect, text
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.database.session import get_db
from app.database.base import Base
from app.models import AppMetadata, Setting
from app.core.security import resolve_within_root


def test_settings_validation():
    config = Settings(_env_file=None, API_PORT=8080, LOG_LEVEL="debug")
    assert config.API_PORT == 8080
    assert config.LOG_LEVEL == "DEBUG"


def test_rejects_invalid_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, API_PORT=70000)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, LOG_LEVEL="verbose")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="production", DEBUG=True, SECRET_KEY="too-short")


def test_sqlite_connection(tmp_path):
    database_file = tmp_path / "nested" / "test.db"
    database_file.parent.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{database_file}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
    assert inspect(engine).has_table("probe")
    engine.dispose()


def test_settings_persist_after_reopening_database(tmp_path):
    engine_url = f"sqlite:///{tmp_path / 'persistent.db'}"
    engine = create_engine(engine_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(Setting.__table__.insert().values(key="theme", value="dark"))
        connection.execute(AppMetadata.__table__.insert().values(key="app", value="OmniDev"))
    engine.dispose()

    reopened = create_engine(engine_url)
    with reopened.connect() as connection:
        assert connection.execute(text("SELECT value FROM settings WHERE key='theme'")).scalar_one() == "dark"
        assert connection.execute(text("SELECT value FROM app_metadata WHERE key='app'")).scalar_one() == "OmniDev"
    reopened.dispose()


def test_database_dependency_closes_session(monkeypatch):
    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr("app.database.session.SessionLocal", lambda: session)
    dependency = get_db()
    assert next(dependency) is session
    try:
        next(dependency)
    except StopIteration:
        pass
    assert session.closed


def test_project_paths_cannot_escape_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    assert resolve_within_root(root, "src/main.py") == (root / "src" / "main.py").resolve()
    with pytest.raises(ValueError):
        resolve_within_root(root, "../outside.txt")
