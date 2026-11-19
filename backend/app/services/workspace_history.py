"""Local workspace snapshots and reviewable file diffs.

Snapshots are stored inside the workspace in .omnidev/history. Symlinks and
generated/dependency directories are deliberately excluded.
"""
from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED = {".git", ".omnidev", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 25_000_000


def _safe_root(root: str | Path) -> Path:
    path = Path(root).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("Workspace root must be an existing directory")
    return path


def _snapshot_dir(root: Path) -> Path:
    directory = root / ".omnidev" / "history" / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _walk_files(root: Path):
    total = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in EXCLUDED and not (current_path / name).is_symlink()
        )
        for name in sorted(names):
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
                continue
            total += size
            yield path


def create_snapshot(root: str | Path, name: str = "Workspace snapshot") -> dict:
    base = _safe_root(root)
    files = {}
    for path in _walk_files(base):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        relative = path.relative_to(base).as_posix()
        files[relative] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content": base64.b64encode(raw).decode("ascii"),
            "size": len(raw),
        }
    snapshot_id = uuid.uuid4().hex
    record = {
        "id": snapshot_id,
        "name": (name or "Workspace snapshot")[:200],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(base),
        "files": files,
        "file_count": len(files),
        "bytes": sum(item["size"] for item in files.values()),
    }
    destination = _snapshot_dir(base) / f"{snapshot_id}.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
    temporary.replace(destination)
    return {key: value for key, value in record.items() if key != "files"}


def load_snapshot(root: str | Path, snapshot_id: str) -> dict:
    if not snapshot_id or any(char not in "0123456789abcdef" for char in snapshot_id):
        raise ValueError("Invalid snapshot ID")
    base = _safe_root(root)
    source = _snapshot_dir(base) / f"{snapshot_id}.json"
    if not source.is_file():
        raise FileNotFoundError("Snapshot not found in this workspace")
    record = json.loads(source.read_text(encoding="utf-8"))
    if Path(record.get("root", "")).resolve() != base:
        raise ValueError("Snapshot belongs to a different workspace")
    return record


def compare_snapshot(root: str | Path, snapshot_id: str) -> dict:
    base = _safe_root(root)
    record = load_snapshot(base, snapshot_id)
    current = {}
    for path in _walk_files(base):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        relative = path.relative_to(base).as_posix()
        current[relative] = raw
    before = record["files"]
    changes = []
    for name in sorted(set(before) | set(current)):
        old = before.get(name)
        new = current.get(name)
        if old and new is None:
            status = "deleted"
        elif old is None and new is not None:
            status = "added"
        elif old["sha256"] != hashlib.sha256(new).hexdigest():
            status = "modified"
        else:
            continue
        item = {"path": name, "status": status,
                "before_size": old["size"] if old else 0,
                "after_size": len(new) if new is not None else 0}
        if status in {"modified", "deleted"}:
            try:
                old_text = base64.b64decode(old["content"]).decode("utf-8").splitlines(True)
                new_text = new.decode("utf-8").splitlines(True) if new is not None else []
                if len(old_text) + len(new_text) <= 4000:
                    item["diff"] = "".join(difflib.unified_diff(
                        old_text, new_text, fromfile=f"a/{name}", tofile=f"b/{name}"
                    ))
            except (UnicodeDecodeError, ValueError):
                item["binary"] = True
        elif status == "added":
            try:
                text = new.decode("utf-8").splitlines(True)
                if len(text) <= 2000:
                    item["diff"] = "".join(difflib.unified_diff(
                        [], text, fromfile="/dev/null", tofile=f"b/{name}"
                    ))
            except UnicodeDecodeError:
                item["binary"] = True
        changes.append(item)
    return {
        "snapshot_id": snapshot_id,
        "snapshot_name": record["name"],
        "created_at": record["created_at"],
        "summary": {
            "changed": len(changes),
            "added": sum(x["status"] == "added" for x in changes),
            "modified": sum(x["status"] == "modified" for x in changes),
            "deleted": sum(x["status"] == "deleted" for x in changes),
        },
        "files": changes,
    }


def restore_snapshot_file(root: str | Path, snapshot_id: str, relative_path: str) -> dict:
    base = _safe_root(root)
    record = load_snapshot(base, snapshot_id)
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("File path escapes the workspace")
    normalized = candidate.relative_to(base).as_posix()
    saved = record["files"].get(normalized)
    if saved is None:
        if candidate.is_file() and not candidate.is_symlink():
            candidate.unlink()
            return {"path": normalized, "action": "deleted"}
        return {"path": normalized, "action": "unchanged"}
    payload = base64.b64decode(saved["content"], validate=True)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.exists() and candidate.is_dir():
        raise ValueError("Cannot restore a file over a directory")
    temporary = candidate.with_name(candidate.name + ".omnidev-restore-tmp")
    temporary.write_bytes(payload)
    temporary.replace(candidate)
    return {"path": normalized, "action": "restored", "bytes": len(payload)}


def restore_snapshot(root: str | Path, snapshot_id: str) -> dict:
    base = _safe_root(root)
    record = load_snapshot(base, snapshot_id)
    preview = compare_snapshot(base, snapshot_id)
    restored = []
    for item in preview["files"]:
        restored.append(restore_snapshot_file(base, snapshot_id, item["path"]))
    return {"snapshot_id": snapshot_id, "restored": restored, "count": len(restored)}
