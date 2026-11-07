"""User-managed provider and command connectors, stored outside source control."""

import json
import os
from threading import RLock
from cryptography.fernet import Fernet
from app.core.config import ROOT_DIR

CONNECTOR_HOME = ROOT_DIR / "connectors"
_lock = RLock()


def _cipher():
    CONNECTOR_HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = CONNECTOR_HOME / "secret.key"
    try:
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(Fernet.generate_key())
    return Fernet(key.read_bytes())


def load_connectors():
    with _lock:
        path = CONNECTOR_HOME / "connections.enc"
        if not path.exists():
            return {"providers": {}, "harnesses": {}}
        return json.loads(_cipher().decrypt(path.read_bytes()))


def public_connector(value):
    return {
        **{k: v for k, v in value.items() if k != "api_key"},
        "has_api_key": bool(value.get("api_key")),
    }


def save_connector(kind, name, value):
    with _lock:
        data = load_connectors()
        previous = data.setdefault(kind, {}).get(name, {})
        # Empty password leaves the saved secret intact. Delete to clear it.
        if kind == "providers" and not value.get("api_key"):
            value["api_key"] = previous.get("api_key", "")
        data[kind][name] = value
        _write(data)
        return public_connector(value)


def delete_connector(kind, name):
    with _lock:
        data = load_connectors()
        if name not in data[kind]:
            return False
        del data[kind][name]
        _write(data)
        return True


def _write(data):
    cipher = _cipher()
    path = CONNECTOR_HOME / "connections.enc"
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(cipher.encrypt(json.dumps(data).encode()))
    temporary.replace(path)
