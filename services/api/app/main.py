from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agents import router as agents_router
from app.github_repositories import router as github_repositories_router
from app.github_webhook import router as github_webhook_router
from app.identity import router as auth_router
from app.pack_catalog import router as pack_catalog_router
from app.products import router as products_router
from app.readiness import check_readiness
from app.teams import router as teams_router


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


app = FastAPI(title="Specbound API")
app.include_router(auth_router)
app.include_router(github_webhook_router)
app.include_router(github_repositories_router)
app.include_router(pack_catalog_router)
app.include_router(agents_router)
app.include_router(products_router)
app.include_router(teams_router)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()


@app.get("/readyz", response_model=HealthResponse)
def readyz() -> HealthResponse:
    try:
        check_readiness()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Service not ready") from exc
    return HealthResponse()
