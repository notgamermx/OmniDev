# API

Start the local API with `python scripts/dev.py`. OpenAPI documentation is served at `/docs`; ReDoc is at `/redoc`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Application name and version |
| GET | `/api/v1/health/` | Service health |
| GET | `/api/v1/system/` | Runtime and platform information |

Future namespaces are documented in the phase roadmap; empty routes are intentionally not registered.
