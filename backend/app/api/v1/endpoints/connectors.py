"""Connect OpenAI-compatible gateways and explicitly chosen command harnesses."""

import re
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, SecretStr, field_validator
import httpx
from app.core.config import settings
from app.services.connector_service import (
    load_connectors,
    save_connector,
    delete_connector,
    public_connector,
)
from app.services.llm_providers import make_provider
from app.services.process_service import run_exec
from app.api.v1.endpoints.workbench import project_path

router = APIRouter(prefix="/connectors")


class ProviderConnection(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(max_length=2000)
    model: str = Field(default="auto", min_length=1, max_length=200)
    api_key: SecretStr = SecretStr("")

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Use an HTTP(S) API base URL without credentials, query or fragment"
            )
        if url.scheme == "http" and url.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Remote provider connections require HTTPS")
        return value.rstrip("/")


class HarnessConnection(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=1, max_length=2000)
    args: list[str] = Field(default_factory=lambda: ["{prompt}"], max_length=100)
    install_command: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("args", "install_command")
    @classmethod
    def valid_args(cls, value):
        if any(not item or len(item) > 10000 or "\x00" in item for item in value):
            raise ValueError("Arguments must be nonempty strings without null bytes")
        return value

    @field_validator("command")
    @classmethod
    def valid_command(cls, value):
        if "\x00" in value:
            raise ValueError("Command contains a null byte")
        return value


class HarnessRun(BaseModel):
    prompt: str = Field(min_length=1, max_length=50000)
    path: str = "."
    timeout: int = Field(default=120, ge=1, le=120)


def validate_id(name):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name):
        raise HTTPException(
            422,
            "Connector ID must use lowercase letters, digits, underscores or hyphens",
        )


def get_connector(kind, name):
    value = load_connectors()[kind].get(name)
    if value is None:
        raise HTTPException(404, "Connector not found")
    return value


@router.get("")
async def list_connections():
    return {
        kind: [
            {"id": name, **public_connector(value)}
            for name, value in rows.items()
            if kind != "providers" or name.startswith("custom_")
        ]
        for kind, rows in load_connectors().items()
        if kind in {"providers", "harnesses"}
    }


@router.put("/providers/{name}")
async def put_provider(name: str, value: ProviderConnection):
    validate_id(name)
    if not name.startswith("custom_"):
        raise HTTPException(422, "Provider connector IDs must start with custom_")
    data = value.model_dump(exclude={"api_key"})
    data["api_key"] = value.api_key.get_secret_value()
    return save_connector("providers", name, data)


@router.get("/providers/{name}/models")
async def provider_models(name: str):
    get_connector("providers", name)
    provider = make_provider(name)
    try:
        response = await provider._client.get("models")
        response.raise_for_status()
        data = response.json()
        return {
            "models": [
                m["id"]
                for m in data.get("data", [])
                if isinstance(m, dict) and isinstance(m.get("id"), str)
            ]
        }
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(
            502,
            "Could not list models. Check the API base URL and key; you can enter a model manually.",
        )
    finally:
        await provider.close()


@router.put("/harnesses/{name}")
async def put_harness(name: str, value: HarnessConnection):
    validate_id(name)
    return save_connector("harnesses", name, value.model_dump())


def require_terminal():
    if not settings.TERMINAL_ENABLED:
        raise HTTPException(
            403, "Enable TERMINAL_ENABLED on the engine to install or run harnesses"
        )


@router.post("/harnesses/{name}/run")
async def run_harness(name: str, value: HarnessRun):
    require_terminal()
    harness = get_connector("harnesses", name)
    argv = [
        harness["command"],
        *[arg.replace("{prompt}", value.prompt) for arg in harness["args"]],
    ]
    if not any("{prompt}" in arg for arg in harness["args"]):
        raise HTTPException(422, "Include {prompt} in a harness argument")
    try:
        return await run_exec(argv, project_path(value.path), value.timeout)
    except OSError:
        raise HTTPException(
            400, "Harness could not start. Install it and check the executable path."
        )


@router.post("/harnesses/{name}/install")
async def install_harness(name: str):
    require_terminal()
    harness = get_connector("harnesses", name)
    if not harness["install_command"]:
        raise HTTPException(
            400,
            "No install command saved. Install the harness using its official instructions.",
        )
    try:
        return await run_exec(harness["install_command"], settings.PROJECT_ROOT, 120)
    except OSError:
        raise HTTPException(
            400,
            "Installer could not start. Check that its package manager is installed.",
        )


@router.delete("/{kind}/{name}")
async def remove_connector(kind: str, name: str):
    if kind not in {"providers", "harnesses"} or not delete_connector(kind, name):
        raise HTTPException(404, "Connector not found")
    return {"deleted": True}
