<!-- coderabbit-ai-generated:v1 -->

# Contributing

Use Python 3.12, Node 24, and the platform-specific Tauri prerequisites. Run `python3.12 scripts/setup.py`, copy `.env.example` to `.env`, and keep keys and local data outside Git.

## Before submitting

```bash
python scripts/version.py
python -m pytest backend/tests -q --cov=app --cov-report=xml
npm ci --prefix apps/desktop/renderer
npm --prefix apps/desktop/renderer test
npm --prefix apps/desktop/renderer run build
```

Build the Docker execution image and set `RUN_DOCKER_TESTS=1` to run isolation tests. Do not weaken sandbox restrictions when the host lacks Docker support. Native Windows and installed-MSI Docker checks require Windows.

Describe the behavior changed, reproduction steps, tests, and any compatibility impact. Keep verification inputs protected and avoid automatic replay of side-effecting tools. Never commit provider keys, engine tokens, logs or generated builds.

## Versions and releases

Edit the version in `pyproject.toml`, run `python scripts/version.py --write`, update the changelog, and commit the resulting manifests. Build with `python scripts/release.py`. Tags must match the version, for example `v1.0.4`. Publish only after required CI and platform checks pass. Configure signing credentials before distributing signed packages; none are included in the repository.
