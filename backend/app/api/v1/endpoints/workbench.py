"""Shared project tools and persistent conversations for desktop, web and CLI."""

import base64
import binascii
import json
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.core.config import settings
from app.core.security import resolve_within_root
from app.database.session import SessionLocal
from app.models.conversation import Conversation

router = APIRouter()


def project_path(path: str = ".") -> Path:
    try:
        return resolve_within_root(settings.PROJECT_ROOT, path)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/workspace")
def workspace():
    return {
        "root": str(settings.PROJECT_ROOT.resolve()),
        "terminal_enabled": settings.TERMINAL_ENABLED,
    }


@router.get("/files")
def files(path: str = "."):
    directory = project_path(path)
    if not directory.is_dir():
        raise HTTPException(404, "Directory not found")
    items = []
    for item in sorted(
        directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
    ):
        try:
            project_path(str(item))
        except HTTPException:
            continue
        items.append(
            {
                "name": item.name,
                "path": item.relative_to(settings.PROJECT_ROOT.resolve()).as_posix(),
                "isDirectory": item.is_dir(),
                "isImage": item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"},
                "size": item.stat().st_size if item.is_file() else None,
            }
        )
    return {"path": path, "items": items}


@router.get("/file")
def read_file(path: str):
    file = project_path(path)
    if not file.is_file():
        raise HTTPException(404, "File not found")
    if file.stat().st_size > 2_000_000:
        raise HTTPException(413, "File is larger than 2 MB")
    try:
        return {"path": path, "content": file.read_text(encoding="utf-8")}
    except UnicodeError as exc:
        raise HTTPException(415, "File is not UTF-8 text") from exc


class FileWrite(BaseModel):
    path: str = Field(min_length=1)
    content: str = Field(max_length=2_000_000)


class FileImport(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    content_base64: str = Field(min_length=1, max_length=14_000_000)
    overwrite: bool = False


@router.post("/files/import")
def import_file(body: FileImport):
    """Import a binary or text file into the current workspace without silent overwrite."""
    try:
        payload = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="The uploaded file is not valid base64 data.") from exc
    if not payload or len(payload) > 10_000_000:
        raise HTTPException(status_code=413, detail="Choose a non-empty file no larger than 10 MB.")
    destination = project_path(body.path)
    if destination.exists() and not body.overwrite:
        raise HTTPException(status_code=409, detail="A file with that name already exists. Rename it or confirm overwrite.")
    if destination.exists() and destination.is_dir():
        raise HTTPException(status_code=409, detail="The destination is a directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if body.overwrite:
        destination.write_bytes(payload)
    else:
        try:
            with destination.open("xb") as imported:
                imported.write(payload)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail="A file with that name already exists.") from exc
    return {
        "path": destination.relative_to(settings.PROJECT_ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "media_type": mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
        "imported": True,
    }


@router.get("/file/base64")
def read_file_base64(path: str):
    """Read a bounded workspace asset for authenticated image preview."""
    file = project_path(path)
    if not file.is_file():
        raise HTTPException(404, "File not found")
    if file.stat().st_size > 10_000_000:
        raise HTTPException(413, "File is larger than 10 MB")
    return {
        "path": path,
        "content_base64": base64.b64encode(file.read_bytes()).decode("ascii"),
        "media_type": mimetypes.guess_type(file.name)[0] or "application/octet-stream",
    }


@router.put("/file")
def write_file(body: FileWrite):
    file = project_path(body.path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(body.content, encoding="utf-8")
    return {"path": body.path, "saved": True}


class Command(BaseModel):
    command: str = Field(min_length=1, max_length=10000)
    path: str = "."
    timeout: int = Field(default=30, ge=1, le=120)


@router.post("/terminal")
async def terminal(body: Command):
    if not settings.TERMINAL_ENABLED:
        raise HTTPException(
            403, "Enable TERMINAL_ENABLED on the server to execute commands"
        )
    cwd = project_path(body.path)
    if not cwd.is_dir():
        raise HTTPException(404, "Directory not found")
    from app.services.process_service import run_command

    return await run_command(body.command, cwd, body.timeout)


class SessionCreate(BaseModel):
    name: str = Field(default="New conversation", min_length=1, max_length=200)


class SessionSave(BaseModel):
    messages: list[dict[str, str]] = Field(max_length=500)


@router.get("/sessions")
def sessions():
    with SessionLocal() as db:
        return {
            "sessions": [
                {"id": s.id, "name": s.name, "updated_at": s.updated_at}
                for s in db.scalars(
                    select(Conversation).order_by(Conversation.updated_at.desc())
                ).all()
            ]
        }


@router.post("/sessions")
def create_session(body: SessionCreate):
    with SessionLocal() as db:
        session = Conversation(
            id=uuid.uuid4().hex,
            name=body.name,
            messages="[]",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return {"id": session.id, "name": session.name, "messages": []}


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    with SessionLocal() as db:
        session = db.get(Conversation, session_id)
        if not session:
            raise HTTPException(404, "Conversation not found")
        return {
            "id": session.id,
            "name": session.name,
            "messages": json.loads(session.messages),
        }


@router.put("/sessions/{session_id}")
def save_session(session_id: str, body: SessionSave):
    encoded = json.dumps(body.messages)
    if len(encoded) > 2_000_000:
        raise HTTPException(413, "Conversation is too large")
    with SessionLocal() as db:
        session = db.get(Conversation, session_id)
        if not session:
            raise HTTPException(404, "Conversation not found")
        session.messages = encoded
        session.updated_at = datetime.now(timezone.utc).isoformat()
        db.commit()
        return {"saved": True}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with SessionLocal() as db:
        session = db.get(Conversation, session_id)
        if not session:
            raise HTTPException(404, "Conversation not found")
        db.delete(session)
        db.commit()
        return {"deleted": True}


class DirectoryCreate(BaseModel):
    path: str = Field(min_length=1, max_length=2000)


@router.post("/directories")
async def create_directory(value: DirectoryCreate):
    directory = project_path(value.path)
    directory.mkdir(parents=True, exist_ok=True)
    return {"path": value.path, "created": True}


class ExecutionPermission(BaseModel):
    enabled: bool


@router.put("/workspace/execution")
async def set_execution_permission(value: ExecutionPermission):
    # The engine API is a trusted workspace; its token grants administration.
    # Defaults remain disabled. This explicit switch lasts until engine restart.
    settings.TERMINAL_ENABLED = value.enabled
    return {"terminal_enabled": settings.TERMINAL_ENABLED}


class SnapshotCreate(BaseModel):
    name: str = Field(default="Workspace snapshot", min_length=1, max_length=200)


class SnapshotRestore(BaseModel):
    confirm: bool = False


class SnapshotFileRestore(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    confirm: bool = False


@router.get("/workspace/snapshots")
def list_workspace_snapshots():
    root = settings.PROJECT_ROOT.resolve()
    directory = root / ".omnidev" / "history" / "snapshots"
    if not directory.is_dir():
        return {"snapshots": []}
    snapshots = []
    for source in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            record = json.loads(source.read_text(encoding="utf-8"))
            snapshots.append({key: record[key] for key in ("id", "name", "created_at", "file_count", "bytes")})
        except (OSError, ValueError, KeyError):
            continue
    return {"snapshots": snapshots}


@router.post("/workspace/snapshots")
def create_workspace_snapshot(body: SnapshotCreate):
    try:
        return create_snapshot(settings.PROJECT_ROOT, body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/workspace/snapshots/{snapshot_id}")
def preview_workspace_snapshot(snapshot_id: str):
    try:
        return compare_snapshot(settings.PROJECT_ROOT, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/workspace/snapshots/{snapshot_id}/restore")
def restore_workspace_snapshot(snapshot_id: str, body: SnapshotRestore):
    if not body.confirm:
        raise HTTPException(409, "Set confirm=true after reviewing the snapshot diff.")
    try:
        return restore_snapshot(settings.PROJECT_ROOT, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/workspace/snapshots/{snapshot_id}/files/restore")
def restore_workspace_snapshot_file(snapshot_id: str, body: SnapshotFileRestore):
    if not body.confirm:
        raise HTTPException(409, "Set confirm=true after reviewing the file diff.")
    try:
        return restore_snapshot_file(settings.PROJECT_ROOT, snapshot_id, body.path)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
