from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

if settings.DATABASE_URL.startswith("sqlite") and settings.DATABASE_URL != "sqlite:///:memory:":
    database_path = settings.DATABASE_URL.removeprefix("sqlite:///").split("?", 1)[0]
    path = Path(database_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def check_database_connection() -> None:
    """Open a short-lived connection to fail early if the database is unavailable."""
    with engine.connect():
        pass
