import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import secrets

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import ApplicationError
from app.database.connection import check_database_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    check_database_connection()
    settings.PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info("AI Development Environment starting")
    # A stopped process cannot resume in-flight model/tool calls safely.
    from sqlalchemy import update
    from app.models.agent import Task
    from app.database.session import SessionLocal
    from sqlalchemy import inspect

    with SessionLocal() as db:
        if inspect(db.bind).has_table("tasks"):
            db.execute(
                update(Task)
                .where(Task.status == "running")
                .values(status="failed", error="Server restarted during execution")
            )
        db.commit()
    yield
    from app.api.v1.endpoints.tasks import workers
    import asyncio

    active = list(workers.values())
    for worker in active:
        worker.cancel()
    await asyncio.gather(*active, return_exceptions=True)
    logger.info("AI Development Environment shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Personal AI Development Environment API",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error while handling %s %s", request.method, request.url.path
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(ApplicationError)
async def application_exception_handler(request: Request, exc: ApplicationError):
    logger.warning(
        "Application error while handling %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Application error"},
    )


@app.get("/")
async def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def authenticate(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if (
            origin
            and origin not in settings.ALLOWED_ORIGINS
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Origin not allowed"}
            )
        if request.method == "OPTIONS":
            return await call_next(request)
        if settings.API_TOKEN:
            expected = "Bearer " + settings.API_TOKEN.get_secret_value()
            if not secrets.compare_digest(
                request.headers.get("authorization", ""), expected
            ):
                return JSONResponse(
                    status_code=401, content={"detail": "API token required"}
                )
    return await call_next(request)


web_dist = (
    Path(__file__).resolve().parents[3] / "apps" / "desktop" / "renderer" / "dist"
)
if not web_dist.is_dir():
    web_dist = Path(__file__).parent / "static"
if web_dist.is_dir():
    app.mount("/app", StaticFiles(directory=web_dist, html=True), name="workbench")
