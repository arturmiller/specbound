from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.teams import router as teams_router


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


app = FastAPI(title="Specbound API")
app.include_router(teams_router)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()
