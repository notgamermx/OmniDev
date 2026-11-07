"""Shared project tools and persistent conversations for desktop, web and CLI."""

import json
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
                "path": str(item.relative_to(settings.PROJECT_ROOT.resolve())),
                "isDirectory": item.is_dir(),
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
