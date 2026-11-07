"""Keep pre-existing verification inputs unchanged during an agent task."""
import hashlib
import os
from pathlib import Path

CONFIG_NAMES = {"conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml", "package.json", "jest.config.js", "vitest.config.js"}


def protected(path: Path) -> bool:
    return bool(set(path.parts) & {"tests", "test", "__tests__"}) or path.name in CONFIG_NAMES or path.name.startswith("test_") or any(x in path.name for x in (".test.", ".spec.")) or path.name.endswith("_test.py")


def snapshot(root):
    root = Path(root).resolve()
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            candidate = Path(directory) / name
            if candidate.is_symlink() and protected(candidate.relative_to(root)):
                raise RuntimeError("Verification inputs must not be symlinks")
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__", "target", "build", "dist"}]
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root)
            if protected(relative):
                if path.is_symlink():
                    raise RuntimeError("Verification inputs must not be symlinks")
                if len(result) >= 5000 or path.stat().st_size > 5_000_000:
                    raise RuntimeError("Verification inputs exceed the snapshot limit")
                result[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def unchanged(root, baseline):
    current = snapshot(root)
    return all(current.get(path) == digest for path, digest in baseline.items())
