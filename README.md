# OmniDev

Personal AI Development Environment backend, built with FastAPI and SQLite.

## Requirements

- Python 3.12

## Install

From the repository root, run the setup script to create `.venv` and install the project plus development tools:

```powershell
py -3.12 scripts/setup.py
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, run `python3.12 scripts/setup.py` and activate with `source .venv/bin/activate`.

## Configure

Copy `.env.example` to `.env` and adjust values as needed. The defaults run locally in development. For other environments, set `ENVIRONMENT` and provide a unique `SECRET_KEY` of at least 32 characters. `.env` is ignored by Git.

SQLite and log paths are created relative to the repository configuration, and the default database path is absolute and stable.

## Initialize and start

Apply the initial database migration, then start the API:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
python scripts/dev.py
```

The API listens at `http://127.0.0.1:8000` by default. Interactive API documentation is at `/docs`.

LLM provider setup and chat API usage are documented in [`integrations/llm_providers/README.md`](integrations/llm_providers/README.md).

## Contributors

- Deejf — project owner
- OpenAI Codex — AI-assisted development

## Test

```powershell
python -m pytest backend/tests -v
```
