import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_migrations_create_schema_and_preserve_data(tmp_path):
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
    subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, text=True)

    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Phase 1-2 tables
        assert {"settings", "app_metadata", "alembic_version"} <= tables
        # Phase 4 tables (projects, workspaces from migration 0003)
        assert {"projects", "workspaces"} <= tables
        # Phase 3 tables (agent engine from migration 0004)
        assert {"agents", "tools", "tasks", "task_steps"} <= tables
        connection.execute("INSERT INTO settings (key, value) VALUES ('persist', 'yes')")
        connection.commit()

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM settings WHERE key='persist'").fetchone()[0] == "yes"
