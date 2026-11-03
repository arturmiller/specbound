from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


app = FastAPI(title="Specbound API")


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()
