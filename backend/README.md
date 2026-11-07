# Backend

The FastAPI application lives in `app/`. Run migrations from the repository root with `python -m alembic -c backend/alembic.ini upgrade head`, then start the server with `python scripts/dev.py`. Backend tests live in `tests/` and run with `python -m pytest backend/tests -v`.
