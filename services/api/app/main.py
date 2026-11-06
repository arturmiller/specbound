from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.agents import router as agents_router
from app.identity import router as auth_router
from app.products import router as products_router
from app.teams import router as teams_router


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


app = FastAPI(title="Specbound API")
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(products_router)
app.include_router(teams_router)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()
