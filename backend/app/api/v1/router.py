from fastapi import APIRouter

from app.api.v1.endpoints import health, system, projects, workspaces, chat, agents, tasks

api_router = APIRouter()
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)
api_router.include_router(
    system.router,
    prefix="/system",
    tags=["System"],
)
api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"],
)
api_router.include_router(
    workspaces.router,
    prefix="/workspaces",
    tags=["Workspaces"],
)
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)
api_router.include_router(
    agents.router,
    prefix="/agents",
    tags=["Agents"],
)
api_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["Tasks"],
)