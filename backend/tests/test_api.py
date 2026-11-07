from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json()["application"]
    assert response.json()["version"]


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_system_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/system/")
    assert response.status_code == 200
    data = response.json()
    assert data["python_version"]
    assert data["platform"]
    assert data["architecture"]
    assert data["environment"]


def test_openapi_docs_are_available():
    with TestClient(app) as client:
        response = client.get("/docs")
    assert response.status_code == 200
