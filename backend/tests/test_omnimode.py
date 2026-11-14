"""Tests for parallel OmniMode execution and binary workspace imports."""

import asyncio
import base64

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_omnimode_runs_specialists_concurrently_then_reviews(
    isolated_service_db, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "API_TOKEN", None)
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path / "projects")
    monkeypatch.setattr(
        "app.services.connector_service.CONNECTOR_HOME", tmp_path / "private"
    )

    active = 0
    maximum_active = 0
    specialist_calls = []
    reviewer_calls = []

    async def fake_complete(provider, model, messages, *, max_tokens, timeout_seconds):
        nonlocal active, maximum_active
        system = messages[0]["content"]
        if "independent verification" in system:
            reviewer_calls.append((provider, model, messages[1]["content"]))
            return "## Final result\nCombined and checked.", {
                "prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50
            }
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            await asyncio.sleep(0.03)
            specialist_calls.append((provider, model))
            return f"Independent result from {model}.", {
                "prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20
            }
        finally:
            active -= 1

    with TestClient(app) as client:
        monkeypatch.setattr(
            "app.api.v1.endpoints.omnimode._complete", fake_complete
        )
        created = []
        for index in range(3):
            response = client.post(
                "/api/v1/agents/",
                json={
                    "name": f"Specialist {index}",
                    "description": f"Focus {index}",
                    "provider": "ollama",
                    "model": f"small-model-{index}",
                    "system_prompt": "Focus on a distinct angle.",
                },
            )
            assert response.status_code == 200, response.text
            created.append(response.json()["id"])

        response = client.post(
            "/api/v1/omnimode/run",
            json={
                "prompt": "Review this implementation plan.",
                "agent_ids": created,
                "reviewer_provider": "ollama",
                "reviewer_model": "nemotron-review",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "completed"
        assert len(payload["specialists"]) == 3
        assert all(item["status"] == "completed" for item in payload["specialists"])
        assert maximum_active == 3
        assert len(reviewer_calls) == 1
        assert "Independent result from small-model-0." in reviewer_calls[0][2]
        assert payload["review"]["status"] == "completed"
        assert payload["verification_scope"] == "model_review_only"


def test_workspace_asset_import_and_no_overwrite_by_default(
    isolated_service_db, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "API_TOKEN", None)
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path / "projects")
    payload = b"\x89PNG\r\n\x1a\nmock-image-bytes"
    encoded = base64.b64encode(payload).decode("ascii")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/files/import",
            json={"path": "assets/test.png", "content_base64": encoded},
        )
        assert response.status_code == 200, response.text
        assert response.json()["bytes"] == len(payload)
        assert (settings.PROJECT_ROOT / "assets" / "test.png").read_bytes() == payload
        conflict = client.post(
            "/api/v1/files/import",
            json={"path": "assets/test.png", "content_base64": encoded},
        )
        assert conflict.status_code == 409
        preview = client.get("/api/v1/file/base64", params={"path": "assets/test.png"})
        assert preview.status_code == 200
        assert preview.json()["content_base64"] == encoded
