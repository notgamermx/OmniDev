"""Exercise the public project and workspace routes together."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_project_and_workspace_routes(isolated_service_db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path / "projects")
    with TestClient(app) as client:
        project = client.post('/api/v1/projects/', json={'name': 'Example'}).json()
        assert project['name'] == 'Example'
        initialized = client.post(f"/api/v1/projects/{project['id']}/workspace")
        assert initialized.status_code == 200, initialized.text
        assert initialized.json()["path"] == str(project["id"])
        assert (settings.PROJECT_ROOT / str(project["id"])).is_dir()
        response = client.post('/api/v1/workspaces/', json={
            'project_id': project['id'], 'name': 'Main', 'path': '.'
        })
        assert response.status_code == 200, response.text
        workspace = response.json()
        assert client.get('/api/v1/projects/').json()['projects'][0]['id'] == project['id']
        assert client.get('/api/v1/workspaces/', params={'project_id': project['id']}).json()['workspaces'][0]['id'] == workspace['id']
        assert client.get('/api/v1/workspaces/', params={'project_id': project['id'] + 1}).json()['workspaces'] == []
        assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 200
        assert client.get(f"/api/v1/workspaces/{workspace['id']}").status_code == 404
