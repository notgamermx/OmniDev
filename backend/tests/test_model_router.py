import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app
from app.services.connector_service import save_connector
from app.services.llm_providers import make_provider, ProviderError
from app.services.model_router import _cooldowns


@pytest.fixture
def client(isolated_service_db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.connector_service.CONNECTOR_HOME", tmp_path / "private"
    )
    monkeypatch.setattr(settings, "API_TOKEN", None)
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path / "projects")
    _cooldowns.clear()
    with TestClient(app) as client:
        yield client
    _cooldowns.clear()


def setup_pool(client):
    for name in ("groq", "cerebras"):
        assert (
            client.put(
                f"/api/v1/models/providers/{name}", json={"api_key": "synthetic-key"}
            ).status_code
            == 200
        )
    routes = [
        {"provider": "groq", "model": "fast"},
        {"provider": "cerebras", "model": "backup"},
    ]
    assert client.put("/api/v1/models/pool", json={"routes": routes}).status_code == 200


def test_setup_secrets_catalog_and_pool_validation(client, monkeypatch, tmp_path):
    setup_pool(client)
    providers = client.get("/api/v1/models/providers").json()
    assert next(p for p in providers if p["id"] == "groq")["configured"]
    assert "synthetic-key" not in json.dumps(providers)
    assert b"synthetic-key" not in (tmp_path / "private/connections.enc").read_bytes()
    assert client.get("/api/v1/connectors").json()["providers"] == []
    assert len(client.get("/api/v1/models/pool").json()["routes"]) == 2
    assert (
        client.put(
            "/api/v1/models/pool",
            json={"routes": [{"provider": "builtin", "model": "auto"}]},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/models/pool",
            json={"routes": [{"provider": "missing", "model": "x"}]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/agents/",
            json={"name": "Integrated", "provider": "builtin", "model": "auto"},
        ).status_code
        == 200
    )

    def transport(req):
        assert req.url.path.endswith("/models")
        assert req.headers["Authorization"] == "Bearer synthetic-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "fast"},
                    {
                        "id": "priced",
                        "pricing": {"prompt": "0.001", "completion": "0.001"},
                    },
                ]
            },
        )

    from app.services.model_router import discover_models

    async def discovery(name):
        return await discover_models(name, transport=httpx.MockTransport(transport))

    monkeypatch.setattr("app.api.v1.endpoints.models.discover_models", discovery)
    models = client.get("/api/v1/models/catalog/groq").json()["models"]
    assert models[0]["id"] == "fast" and models[1]["free"] is False
    client.delete("/api/v1/models/providers/groq")
    assert not next(
        p for p in client.get("/api/v1/models/providers").json() if p["id"] == "groq"
    )["has_saved_key"]


@pytest.mark.asyncio
async def test_pool_rate_limit_fallback_and_cooldown(client):
    setup_pool(client)
    calls = []

    def transport(req):
        payload = json.loads(req.content)
        calls.append(payload["model"])
        if payload["model"] == "fast":
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={"model": "backup", "choices": [{"message": {"content": "works"}}]},
        )

    pool = make_provider("builtin", transport=httpx.MockTransport(transport))
    result = await pool.chat_completion(
        model="auto", messages=[{"role": "user", "content": "hi"}]
    )
    assert result["routed_provider"] == "cerebras"
    assert calls == ["fast", "backup"]
    await pool.chat_completion(model="auto", messages=[])
    assert calls == ["fast", "backup", "backup"]
    with pytest.raises(ProviderError):
        await pool.chat_completion(model="unknown", messages=[])


@pytest.mark.asyncio
async def test_stream_fails_over_before_first_event(client):
    setup_pool(client)
    calls = []

    def transport(req):
        model = json.loads(req.content)["model"]
        calls.append(model)
        if model == "fast":
            return httpx.Response(503)
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n',
        )

    pool = make_provider("builtin", transport=httpx.MockTransport(transport))
    chunks = [c async for c in pool.chat_completion_stream(model="auto", messages=[])]
    assert calls == ["fast", "backup"]
    assert chunks[0]["routed_provider"] == "cerebras"


@pytest.mark.asyncio
async def test_stream_never_splices_partial_responses(client):
    setup_pool(client)
    calls = []

    class Broken(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            raise httpx.ReadError("interrupted")

    def transport(req):
        calls.append(json.loads(req.content)["model"])
        return httpx.Response(200, stream=Broken())

    pool = make_provider("builtin", transport=httpx.MockTransport(transport))
    chunks = []
    with pytest.raises(ProviderError):
        async for chunk in pool.chat_completion_stream(model="auto", messages=[]):
            chunks.append(chunk)
    assert calls == ["fast"] and len(chunks) == 1


def test_builtin_chat_endpoint_and_empty_setup(client, monkeypatch):
    payload = {
        "provider": "builtin",
        "model": "auto",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    assert client.post("/api/v1/chat/completions/", json=payload).status_code == 400
    setup_pool(client)

    def factory(name):
        return make_provider(
            name,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200,
                    json={
                        "model": "fast",
                        "choices": [
                            {"message": {"role": "assistant", "content": "Hello"}}
                        ],
                    },
                )
            ),
        )

    monkeypatch.setattr("app.api.v1.endpoints.chat.make_provider", factory)
    data = client.post("/api/v1/chat/completions/", json=payload).json()
    assert data["routed_provider"] == "groq" and data["model"] == "fast"
    pool = client.get("/api/v1/models/pool").json()
    for r in pool["routes"]:
        r["enabled"] = False
    client.put("/api/v1/models/pool", json=pool)
    assert client.post("/api/v1/chat/completions/", json=payload).status_code == 400


@pytest.mark.asyncio
async def test_pool_falls_back_on_malformed_provider_response(client):
    setup_pool(client)
    calls = []

    def transport(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "fast":
            return httpx.Response(200, text="invalid-json")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "recovered"}}]}
        )

    pool = make_provider("builtin", transport=httpx.MockTransport(transport))
    assert (await pool.chat_completion(model="auto", messages=[]))[
        "routed_provider"
    ] == "cerebras"
    assert calls == ["fast", "backup"]
