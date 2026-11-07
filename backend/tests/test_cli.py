from argparse import Namespace
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('omnidev_cli', Path(__file__).resolve().parents[2] / 'cli' / 'main.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_memory_subcommands_dispatch(capsys):
    class Client:
        def get_session_memory(self, key):
            return {'key': key, 'value': 'saved'}

        def set_session_memory(self, key, value, data):
            return {'key': key, 'value': value, 'data': data}

    assert cli.cmd_memory_session(Client(), Namespace(subaction='set', key='k', value='v', data=None)) == 0
    assert '"value": "v"' in capsys.readouterr().out
    assert cli.cmd_memory_session(Client(), Namespace(subaction='get', key='k')) == 0
    assert '"value": "saved"' in capsys.readouterr().out
    assert cli.cmd_memory_session(Client(), Namespace(subaction='get', key=None)) == 1


def test_desktop_discovery_does_not_send_local_token_to_remote(monkeypatch):
    import httpx
    import app.cli as application_cli
    original_client = httpx.Client
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"status":"healthy"})

    monkeypatch.delenv("OMNIDEV_TOKEN", raising=False)
    monkeypatch.delenv("OMNIDEV_URL", raising=False)
    monkeypatch.setattr(application_cli, "_desktop_connection", lambda: {"url":"http://127.0.0.1:12345", "token":"synthetic-desktop-token"})
    monkeypatch.setattr(application_cli.httpx, "Client", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("sys.argv", ["omnidev", "health"])
    assert application_cli.main() == 0
    assert sent[-1].headers["Authorization"] == "Bearer synthetic-desktop-token"
    monkeypatch.setattr("sys.argv", ["omnidev", "--url", "https://remote.example", "health"])
    assert application_cli.main() == 0
    assert "Authorization" not in sent[-1].headers


def test_connector_file_dispatch(monkeypatch, tmp_path):
    import httpx
    import app.cli as application_cli
    original_client = httpx.Client
    definition = {"name":"Gateway", "base_url":"http://127.0.0.1:3001/v1", "api_key":"synthetic-key"}
    path = tmp_path / "connection.json"
    import json
    path.write_text(json.dumps(definition))
    sent = []
    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"saved":True})
    monkeypatch.setattr(application_cli.httpx, "Client", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr("sys.argv", ["omnidev", "connectors", "save", "providers", "custom_free", "--file", str(path)])
    assert application_cli.main() == 0
    assert sent[-1].method == "PUT"
    assert sent[-1].url.path == "/api/v1/connectors/providers/custom_free"
    assert json.loads(sent[-1].content) == definition
