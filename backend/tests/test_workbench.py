import json
import sys
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.core.config import settings
from app.main import app


@pytest.fixture
def client(isolated_service_db, tmp_path, monkeypatch):
    # API/process semantics use a local test transport; isolation has dedicated Docker tests.
    from app.services.process_service import _run_host_command
    monkeypatch.setattr("app.services.process_service.run_command", _run_host_command)
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(settings, "API_TOKEN", None)
    with TestClient(app) as client:
        yield client


def test_files_are_scoped_and_sessions_persist(client, tmp_path):
    assert (
        client.put(
            "/api/v1/file", json={"path": "src/example.py", "content": "print(42)"}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/file", params={"path": "src/example.py"}).json()["content"]
        == "print(42)"
    )
    assert (
        client.get("/api/v1/files", params={"path": "src"}).json()["items"][0]["path"]
        == "src/example.py"
    )
    # Explorer navigates using the returned paths, including nested directories.
    assert client.post("/api/v1/directories", json={"path": "src/nested"}).status_code == 200
    assert client.put("/api/v1/file", json={"path": "src/nested/file.txt", "content": "nested"}).status_code == 200
    entries = client.get("/api/v1/files", params={"path": "src"}).json()["items"]
    folder = next(item for item in entries if item["isDirectory"])
    assert folder["path"] == "src/nested"
    nested = client.get("/api/v1/files", params={"path": folder["path"]}).json()["items"][0]
    assert nested["path"] == "src/nested/file.txt"
    assert client.get("/api/v1/file", params={"path": nested["path"]}).json()["content"] == "nested"
    assert client.get("/api/v1/file", params={"path": "../outside"}).status_code == 403
    assert (
        client.put(
            "/api/v1/file", json={"path": "../outside", "content": "bad"}
        ).status_code
        == 403
    )
    session = client.post("/api/v1/sessions", json={"name": "Shared"}).json()
    messages = [{"role": "user", "content": "hello"}]
    assert (
        client.put(
            "/api/v1/sessions/" + session["id"], json={"messages": messages}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/sessions/" + session["id"]).json()["messages"] == messages
    )
    assert client.get("/api/v1/sessions").json()["sessions"][0]["id"] == session["id"]
    assert client.delete("/api/v1/sessions/" + session["id"]).status_code == 200
    assert client.get("/api/v1/sessions/" + session["id"]).status_code == 404


def test_auth_and_browser_origin(client, monkeypatch):
    monkeypatch.setattr(settings, "API_TOKEN", SecretStr("x" * 32))
    assert client.get("/api/v1/workspace").status_code == 401
    assert (
        client.get(
            "/api/v1/workspace", headers={"Authorization": "Bearer " + "x" * 32}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/sessions",
            json={},
            headers={
                "Origin": "https://untrusted.example",
                "Authorization": "Bearer " + "x" * 32,
            },
        ).status_code
        == 403
    )


def test_terminal_permission_and_exit_status(client, monkeypatch):
    monkeypatch.setattr(settings, "TERMINAL_ENABLED", False)
    assert (
        client.post("/api/v1/terminal", json={"command": "echo hello"}).status_code
        == 403
    )
    monkeypatch.setattr(settings, "TERMINAL_ENABLED", True)
    result = client.post(
        "/api/v1/terminal", json={"command": f'"{sys.executable}" -c "print(42)"'}
    ).json()
    assert result["exit_code"] == 0 and "42" in result["output"]
    result = client.post(
        "/api/v1/terminal",
        json={
            "command": f'"{sys.executable}" -c "import time;time.sleep(10)"',
            "timeout": 1,
        },
    ).json()
    assert result["timed_out"] and result["exit_code"] != 0


def test_agent_writes_application_and_verifies_before_completion(
    client, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "TERMINAL_ENABLED", True)
    plans = iter(
        [
            'ACTION: write_file {"path":"hello.py","content":"print(42)"}',
            "COMPLETE: Created hello application",
        ]
    )

    class Provider:
        async def chat_completion(self, **kwargs):
            return {"choices": [{"message": {"content": next(plans)}}]}

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.services.agent_engine.make_provider", lambda name: Provider()
    )
    agent = client.post(
        "/api/v1/agents/",
        json={
            "name": "Builder",
            "provider": "ollama",
            "model": "test",
            "tool_names": ["write_file", "shell"],
        },
    ).json()
    task = client.post(
        "/api/v1/tasks/",
        json={
            "agent_id": agent["id"],
            "title": "Build hello",
            "verification_command": f'"{sys.executable}" hello.py',
        },
    ).json()
    result = client.post(
        f"/api/v1/tasks/{task['id']}/execute", json={"project_root": "."}
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "completed"
    assert (tmp_path / "hello.py").read_text() == "print(42)"
    details = client.get(f"/api/v1/tasks/{task['id']}").json()
    verification = [s for s in details["steps"] if s["tool_name"] == "shell"]
    assert json.loads(verification[-1]["tool_result"])["result"]["exit_code"] == 0


def test_session_memory_isolation(client):
    client.post(
        "/api/v1/memory/session",
        json={"session_id": "one", "key": "name", "value": "first"},
    )
    client.post(
        "/api/v1/memory/session",
        json={"session_id": "two", "key": "name", "value": "second"},
    )
    assert (
        client.get("/api/v1/memory/session?session_id=one").json()["memories"][0][
            "value"
        ]
        == "first"
    )
    client.delete("/api/v1/memory/session/name?session_id=one")
    assert (
        client.get("/api/v1/memory/session/name?session_id=two").json()["value"]
        == "second"
    )


def test_desktop_authenticated_preflight(client, monkeypatch):
    monkeypatch.setattr(settings, "API_TOKEN", SecretStr("x" * 32))
    response = client.options(
        "/api/v1/workspace",
        headers={
            "Origin": "http://tauri.localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_failed_verification_prevents_completion_and_agent_repairs(client, monkeypatch):
    monkeypatch.setattr(settings, "TERMINAL_ENABLED", True)
    plans = iter(
        [
            'ACTION: write_file {"path":"answer.py","content":"value = 0"}',
            "COMPLETE: done",
            'ACTION: write_file {"path":"answer.py","content":"value = 42"}',
            "COMPLETE: repaired",
        ]
    )

    class Provider:
        async def chat_completion(self, **kwargs):
            return {"choices": [{"message": {"content": next(plans)}}]}

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.services.agent_engine.make_provider", lambda name: Provider()
    )
    agent = client.post(
        "/api/v1/agents/",
        json={
            "name": "Repairer",
            "provider": "ollama",
            "model": "test",
            "tool_names": ["write_file", "shell"],
        },
    ).json()
    task = client.post(
        "/api/v1/tasks/",
        json={
            "agent_id": agent["id"],
            "title": "Answer",
            "verification_command": f'"{sys.executable}" -c "import answer; assert answer.value == 42"',
        },
    ).json()
    result = client.post(
        f"/api/v1/tasks/{task['id']}/execute", json={"project_root": "."}
    ).json()
    assert result["status"] == "completed" and result["result"] == "repaired"
    steps = client.get(f"/api/v1/tasks/{task['id']}").json()["steps"]
    verification = [
        json.loads(s["tool_result"])["result"]["exit_code"]
        for s in steps
        if s["tool_name"] == "shell"
    ]
    assert verification[0] != 0 and verification[1] == 0


@pytest.mark.asyncio
async def test_agent_provider_failover_closes_failed_provider(monkeypatch):
    from types import SimpleNamespace
    from app.services.agent_engine import AgentEngine
    from app.services.llm_providers import ProviderError

    monkeypatch.setattr(
        settings, "PROVIDER_FALLBACKS", [{"provider": "groq", "model": "backup"}]
    )
    closed = []

    class Provider:
        def __init__(self, name):
            self.name = name

        async def chat_completion(self, **kwargs):
            if self.name == "ollama":
                raise ProviderError("Unavailable")
            assert kwargs["model"] == "backup"
            return {"choices": [{"message": {"content": "COMPLETE: recovered"}}]}

        async def close(self):
            closed.append(self.name)

    monkeypatch.setattr(
        "app.services.agent_engine.make_provider", lambda name: Provider(name)
    )
    context = SimpleNamespace(
        agent_model=SimpleNamespace(provider="ollama", model="primary", temperature=0),
        context_manager=SimpleNamespace(get_prompt=lambda: []),
    )
    context.token_spent = 0
    assert await AgentEngine()._plan_step(context) == "COMPLETE: recovered"
    assert closed == ["ollama", "groq"]
