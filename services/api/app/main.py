import logging
import os
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.agents import router as agents_router
from app.assessment_reports import router as assessment_reports_router
from app.database import get_engine
from app.evidence_registry import router as evidence_registry_router
from app.github_repositories import router as github_repositories_router
from app.github_webhook import router as github_webhook_router
from app.identity import router as auth_router
from app.metrics import render_metrics
from app.overview import router as overview_router
from app.pack_catalog import router as pack_catalog_router
from app.products import router as products_router
from app.provider_test_runs import router as provider_test_runs_router
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
app.include_router(assessment_reports_router)
app.include_router(overview_router)
app.include_router(evidence_registry_router)
app.include_router(products_router)
app.include_router(provider_test_runs_router)
app.include_router(teams_router)

request_logger = logging.getLogger("specbound.http")


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        request_logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
            },
        )


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


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics():
    if os.environ.get("METRICS_ENABLED", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        with get_engine().connect() as db:
            output = render_metrics(db, now=datetime.now(timezone.utc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Metrics unavailable") from exc
    return PlainTextResponse(output, media_type="text/plain; version=0.0.4")
