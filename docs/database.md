# Database

SQLite is stored at the absolute path configured by `DATABASE_URL` (the default is `<repository>/data/app.db`). SQLAlchemy models inherit from `app.database.base.Base`; API dependencies should obtain sessions through `app.database.session.get_db`.

The initial schema contains `settings` and `app_metadata`. Apply schema changes with Alembic, never `Base.metadata.create_all()` in the application startup path:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
```
