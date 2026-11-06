"""Receive and persist authenticated GitHub deliveries without session auth."""

import json
import os
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import JSON, bindparam, select, text
from sqlalchemy.engine import Connection

from app.database import get_connection
from app.github_source import verify_github_signature
from app.tables import github_events

router = APIRouter()
MAX_BODY = 2 * 1024 * 1024


def list_github_events(db: Connection, delivery_id: str):
    return list(
        db.execute(
            select(github_events).where(github_events.c.delivery_id == delivery_id)
        ).mappings()
    )


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request, db: Annotated[Connection, Depends(get_connection)]
):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="Webhook body too large")
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode("utf-8")
    if not verify_github_signature(
        secret, bytes(body), request.headers.get("x-hub-signature-256", "")
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    installation = os.environ.get("GITHUB_INSTALLATION_ID", "")
    organization = os.environ.get("GITHUB_ORGANIZATION_ID", "")
    try:
        organization = str(UUID(organization))
    except ValueError as exc:
        raise HTTPException(
            status_code=503, detail="GitHub organization is not configured"
        ) from exc
    if not installation.isdecimal():
        raise HTTPException(
            status_code=503, detail="GitHub installation is not configured"
        )
    try:
        delivery = str(UUID(request.headers.get("x-github-delivery", "")))
        event_type = request.headers.get("x-github-event", "")
        if not re.fullmatch(r"[a-z_]{1,100}", event_type):
            raise ValueError("invalid event")
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("installation"), dict
        ):
            raise ValueError("invalid payload")
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError) as exc:
        raise HTTPException(status_code=400, detail="Invalid GitHub delivery") from exc
    if str(payload["installation"].get("id", "")) != installation:
        raise HTTPException(status_code=403, detail="Unexpected installation")
    db.execute(
        text(
            "INSERT INTO github_events (delivery_id, installation_id, organization_id, event_type, payload) VALUES (:delivery, :installation, :organization, :event, :payload) ON CONFLICT DO NOTHING"
        ).bindparams(bindparam("payload", type_=JSON)),
        {
            "delivery": delivery,
            "installation": installation,
            "organization": organization,
            "event": event_type,
            "payload": payload,
        },
    )
