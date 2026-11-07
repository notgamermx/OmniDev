import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_migrations_create_schema_and_preserve_data(tmp_path):
    """Test that migrations create all expected tables and can preserve data."""
    db_path = tmp_path / "migrated.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    command = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ROOT / "backend" / "alembic.ini"),
        "upgrade",
        "head",
    ]

    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Phase 1-2 tables
        assert {"settings", "app_metadata", "alembic_version"} <= tables
        # Phase 4 tables (projects, workspaces from migration 0003)
        assert {"projects", "workspaces"} <= tables
        # Phase 3 tables (agent engine from migration 0004)
        assert {"agents", "tools", "tasks", "task_steps"} <= tables
        # Phase 5 tables (memory system from migration 0005)
        assert {"session_memories", "project_memories", "long_term_preferences", "context_retrievals", "project_understandings"} <= tables
        assert {"shared_sessions", "shared_session_memberships", "websocket_sessions"} <= tables
        connection.execute("INSERT INTO settings (key, value) VALUES ('persist', 'yes')")
        connection.commit()

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM settings WHERE key='persist'").fetchone()[0] == "yes"


def test_upgrade_existing_agent_database(tmp_path):
    db_path = tmp_path / "existing.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    command = [sys.executable, "-m", "alembic", "-c", str(ROOT / "backend" / "alembic.ini"), "upgrade"]
    first = subprocess.run(command + ["0004_agent_engine"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    with sqlite3.connect(db_path) as connection:
        connection.execute("INSERT INTO settings (key, value) VALUES ('existing', 'value')")
        connection.commit()
    upgrade = subprocess.run(command + ["head"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert upgrade.returncode == 0, upgrade.stderr
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM settings WHERE key='existing'").fetchone()[0] == 'value'
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == '0007_conversations'
