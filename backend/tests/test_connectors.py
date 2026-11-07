import json
import sys
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app
from app.services.llm_providers import make_provider


@pytest.fixture
def client(isolated_service_db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.connector_service.CONNECTOR_HOME", tmp_path / "private"
    )
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(settings, "TERMINAL_ENABLED", False)
    monkeypatch.setattr(settings, "API_TOKEN", None)
    with TestClient(app) as client:
        yield client


def save_provider(client):
    return client.put(
        "/api/v1/connectors/providers/custom_free",
        json={
            "name": "Free gateway",
            "base_url": "http://127.0.0.1:3001/v1",
            "api_key": "synthetic-secret",
            "model": "auto:fast",
        },
    )


def test_secrets_encrypted_and_custom_provider_available_to_agents(client, tmp_path):
    assert save_provider(client).status_code == 200
    listing = client.get("/api/v1/connectors").json()
    assert listing["providers"][0]["has_api_key"]
    assert "synthetic-secret" not in json.dumps(listing)
    assert (
        b"synthetic-secret" not in (tmp_path / "private/connections.enc").read_bytes()
    )
    assert any(
        p["name"] == "custom_free" for p in client.get("/api/v1/chat/providers/").json()
    )
    assert (
        client.post(
            "/api/v1/agents/",
            json={"name": "Connected", "provider": "custom_free", "model": "auto"},
        ).status_code
        == 200
    )
    assert client.delete("/api/v1/connectors/providers/custom_free").status_code == 200
    assert (
        client.post(
            "/api/v1/chat/completions/",
            json={"provider": "custom_free", "model": "auto", "messages": []},
        ).status_code
        == 404
    )


@pytest.mark.asyncio
async def test_custom_gateway_transport_and_secret_preservation(client):
    save_provider(client)
    client.put(
        "/api/v1/connectors/providers/custom_free",
        json={
            "name": "Updated",
            "base_url": "http://127.0.0.1:3001/v1",
            "api_key": "",
            "model": "auto",
        },
    )

    def transport(request):
        assert str(request.url) == "http://127.0.0.1:3001/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-secret"
        assert json.loads(request.content)["model"] == "auto:fast"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Hello"}}]}
        )

    provider = make_provider("custom_free", transport=httpx.MockTransport(transport))
    try:
        result = await provider.chat_completion(
            model="auto:fast", messages=[{"role": "user", "content": "Hello"}]
        )
        assert result["choices"][0]["message"]["content"] == "Hello"
    finally:
        await provider.close()


def test_provider_validation_and_model_discovery(client, monkeypatch):
    assert (
        client.put(
            "/api/v1/connectors/providers/openai",
            json={"name": "x", "base_url": "https://example.com/v1"},
        ).status_code
        == 422
    )
    for url in [
        "file:///tmp/key",
        "http://example.com/v1",
        "https://user:key@example.com/v1",
        "https://example.com/v1?key=secret",
    ]:
        assert (
            client.put(
                "/api/v1/connectors/providers/custom_bad",
                json={"name": "x", "base_url": url},
            ).status_code
            == 422
        )
    save_provider(client)

    def factory(name):
        return make_provider(
            name,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, json={"data": [{"id": "auto"}, {"id": "auto:fast"}]}
                )
            ),
        )

    monkeypatch.setattr("app.api.v1.endpoints.connectors.make_provider", factory)
    assert client.get("/api/v1/connectors/providers/custom_free/models").json() == {
        "models": ["auto", "auto:fast"]
    }


def test_harness_install_run_scope_and_permissions(client, tmp_path):
    script = tmp_path / "harness.py"
    script.write_text(
        "import sys,pathlib;pathlib.Path('result.txt').write_text(sys.argv[1]);print(sys.argv[1])"
    )
    definition = {
        "name": "Test harness",
        "command": sys.executable,
        "args": [str(script), "{prompt}"],
        "install_command": [sys.executable, "-c", "print('installer works')"],
    }
    assert (
        client.put("/api/v1/connectors/harnesses/test", json=definition).status_code
        == 200
    )
    url = "/api/v1/connectors/harnesses/test"
    assert client.post(url + "/run", json={"prompt": "hello"}).status_code == 403
    assert client.post(url + "/install").status_code == 403
    assert (
        client.put("/api/v1/workspace/execution", json={"enabled": True}).status_code
        == 200
    )
    assert client.post("/api/v1/directories", json={"path": "demo"}).status_code == 200
    prompt = 'quote " ; & literal $(echo unsafe)'
    result = client.post(url + "/run", json={"prompt": prompt, "path": "demo"}).json()
    assert result["exit_code"] == 0 and prompt in result["output"]
    assert (settings.PROJECT_ROOT / "demo/result.txt").read_text() == prompt
    assert (
        client.post(
            url + "/run", json={"prompt": "hi", "path": "../../outside"}
        ).status_code
        == 403
    )
    assert client.post(url + "/install").json()["exit_code"] == 0
    assert (
        client.post("/api/v1/directories", json={"path": "../../outside"}).status_code
        == 403
    )
    client.put("/api/v1/workspace/execution", json={"enabled": False})
    assert client.post(url + "/run", json={"prompt": "hello"}).status_code == 403
