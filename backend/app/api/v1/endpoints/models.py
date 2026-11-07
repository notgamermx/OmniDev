"""Built-in provider setup and model routing, shared by desktop, web and CLI."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, SecretStr, model_validator
from app.core.config import settings
from app.services.connector_service import (
    load_connectors,
    save_connector,
    delete_connector,
)
from app.services.llm_providers import (
    PROVIDERS,
    PROVIDER_BY_ID,
    has_provider,
    ProviderError,
    MissingProviderCredential,
)
from app.services.model_router import configured, discover_models, pool_routes

router = APIRouter(prefix="/models")


class Credentials(BaseModel):
    api_key: SecretStr = SecretStr("")
    account_id: str = Field(default="", max_length=200)


class Route(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=300)
    enabled: bool = True

    @model_validator(mode="after")
    def valid_provider(self):
        if self.provider == "builtin" or not has_provider(self.provider):
            raise ValueError(
                "Choose a registered provider; the router cannot route to itself"
            )
        return self


class Pool(BaseModel):
    routes: list[Route] = Field(max_length=50)


@router.get("/providers")
async def providers():
    saved = load_connectors()["providers"]
    return [
        {
            "id": p.id,
            "name": p.name,
            "configured": configured(p.id, settings),
            "has_saved_key": bool(saved.get(p.id, {}).get("api_key")),
            "account_id_required": bool(p.account_id_env),
            "signup_url": p.connect_url,
            "tier": p.free_access,
        }
        for p in PROVIDERS
    ]


@router.put("/providers/{provider_id}")
async def credentials(provider_id: str, value: Credentials):
    if provider_id not in PROVIDER_BY_ID:
        raise HTTPException(404, "Unknown built-in provider")
    save_connector(
        "providers",
        provider_id,
        {"api_key": value.api_key.get_secret_value(), "account_id": value.account_id},
    )
    return {"saved": True, "configured": configured(provider_id, settings)}


@router.delete("/providers/{provider_id}")
async def remove_credentials(provider_id: str):
    if provider_id not in PROVIDER_BY_ID:
        raise HTTPException(404, "Unknown built-in provider")
    delete_connector("providers", provider_id)
    return {"deleted": True, "configured": configured(provider_id, settings)}


@router.get("/catalog/{provider_id}")
async def catalog(provider_id: str):
    if not has_provider(provider_id):
        raise HTTPException(404, "Unknown provider")
    try:
        return {"models": await discover_models(provider_id)}
    except MissingProviderCredential as exc:
        raise HTTPException(400, str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/pool")
async def pool():
    return {"routes": pool_routes()}


@router.put("/pool")
async def set_pool(value: Pool):
    save_connector("routing", "pool", value.model_dump())
    return value
