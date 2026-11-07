import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.llm_providers import PROVIDERS


def test_provider_endpoint_lists_catalog():
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/providers/")
    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == ({item.id for item in PROVIDERS} | {"builtin"})
    assert "configured" in response.json()[0]


def test_completion_uses_provider_factory_and_normalizes_response(monkeypatch):
    class FakeProvider:
        async def chat_completion(self, **kwargs):
            assert kwargs["model"] == "model-x"
            return {
                "id": "reply-1",
                "model": "model-x",
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            }

        async def close(self):
            pass

    monkeypatch.setattr("app.api.v1.endpoints.chat.make_provider", lambda provider_id: FakeProvider())
    payload = {"provider": "google_gemini", "model": "model-x", "messages": [{"role": "user", "content": "hi"}]}
    with TestClient(app) as client:
        response = client.post("/api/v1/chat/completions/", json=payload)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hello"
    assert response.json()["provider"] == "google_gemini"


def test_completion_reports_missing_api_key_safely(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    payload = {"provider": "google_gemini", "model": "model-x", "messages": [{"role": "user", "content": "hi"}]}
    with TestClient(app) as client:
        response = client.post("/api/v1/chat/completions/", json=payload)
    assert response.status_code == 400
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_streaming_endpoint_emits_sse_and_closes_provider(monkeypatch):
    class FakeProvider:
        closed = False

        async def chat_completion_stream(self, **kwargs):
            yield {"choices": [{"delta": {"content": "hi"}}]}

        async def close(self):
            self.closed = True

    provider = FakeProvider()
    monkeypatch.setattr("app.api.v1.endpoints.chat.make_provider", lambda provider_id: provider)
    payload = {"provider": "ollama", "model": "llama3.1:8b", "messages": [{"role": "user", "content": "hi"}]}
    with TestClient(app) as client:
        response = client.post("/api/v1/chat/completions/stream", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert json.loads(response.text.split("data: ")[1].split("\n")[0])["choices"][0]["delta"]["content"] == "hi"
    assert "data: [DONE]" in response.text
    assert provider.closed
