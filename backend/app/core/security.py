from pathlib import Path


def resolve_within_root(root: Path, requested_path: str | Path) -> Path:
    """Resolve a path and reject traversal outside the configured project root."""
    resolved_root = root.resolve()
    candidate = (resolved_root / requested_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Path must stay within the configured project root") from exc
    return candidate
