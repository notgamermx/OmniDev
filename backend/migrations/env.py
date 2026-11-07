from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database.base import Base
from app.models.settings import Setting
from app.models.metadata import AppMetadata
from app.core.config import settings

# Interpret the config file for Python logging.
# This line sets up loggers basically.
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
if settings.DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = Path(settings.DATABASE_URL.removeprefix("sqlite:///").split("?", 1)[0])
    if not sqlite_path.is_absolute():
        sqlite_path = ROOT_DIR / sqlite_path
    # Keep SQLite file paths usable when the data directory is not yet present.
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

# add model's MetaData for 'autogenerate support'
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
