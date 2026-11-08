"""Verify RFC 9068 access tokens and resolve stable user principals."""

import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.database import get_connection

AGENT_TOKEN_ISSUER = "urn:specbound:local-agent-credential"


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    jwks_url: str
    client_id: str
    audience: str


def _trusted_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return bool(
            parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and not parsed.query
            and (
                parsed.scheme == "https"
                or (
                    parsed.scheme == "http"
                    and parsed.hostname in ("localhost", "127.0.0.1", "::1")
                )
            )
        )
    except ValueError:
        return False


def oidc_config() -> OidcConfig | None:
    issuer = os.environ.get("OIDC_ISSUER", "").strip()
    jwks_url = os.environ.get("OIDC_JWKS_URL", "").strip()
    client_id = os.environ.get("OIDC_CLIENT_ID", "").strip()
    audience = os.environ.get("OIDC_AUDIENCE", "").strip()
    if not all((issuer, jwks_url, client_id, audience)):
        return None
    local_jwks = (
        os.environ.get("SPECBOUND_LOCAL_DEV_OIDC") == "1"
        and issuer == "http://127.0.0.1:15556"
        and jwks_url == "http://local-oidc:5556/jwks"
    )
    if (
        not _trusted_url(issuer)
        or (not _trusted_url(jwks_url) and not local_jwks)
        or client_id == audience
    ):
        return None
    if urlsplit(issuer).scheme == "https" and urlsplit(jwks_url).scheme != "https":
        return None
    return OidcConfig(issuer, jwks_url, client_id, audience)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Invalid or unavailable authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=8)
def _jwk_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, timeout=5)


def verify_access_token(request: Request) -> tuple[str, str]:
    config = oidc_config()
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split()
    if (
        config is None
        or len(parts) != 2
        or parts[0].lower() != "bearer"
        or len(parts[1]) > 8192
    ):
        raise _unauthorized()
    token = parts[1]
    if token.startswith("sba_"):
        if not re.fullmatch(r"sba_[A-Za-z0-9_-]{43}", token):
            raise _unauthorized()
        return AGENT_TOKEN_ISSUER, hashlib.sha256(token.encode("ascii")).hexdigest()
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or str(header.get("typ", "")).lower()
            not in ("at+jwt", "application/at+jwt")
            or not isinstance(header.get("kid"), str)
            or not header["kid"]
            or header.get("crit")
        ):
            raise _unauthorized()
        signing_key = _jwk_client(config.jwks_url).get_signing_key_from_jwt(token)
        if signing_key.algorithm_name != "RS256":
            raise _unauthorized()
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=config.issuer,
            audience=config.audience,
            options={
                "require": [
                    "iss",
                    "sub",
                    "aud",
                    "exp",
                    "iat",
                    "jti",
                    "client_id",
                    "scope",
                ]
            },
        )
        if (
            not isinstance(claims["sub"], str)
            or not claims["sub"].strip()
            or not claims["sub"].isascii()
            or len(claims["sub"]) > 255
            or "\0" in claims["sub"]
            or not isinstance(claims["iat"], int)
            or isinstance(claims["iat"], bool)
            or not isinstance(claims["exp"], int)
            or isinstance(claims["exp"], bool)
            or not isinstance(claims["jti"], str)
            or not claims["jti"].strip()
            or claims["client_id"] != config.client_id
            or not isinstance(claims["scope"], str)
            or "openid" not in claims["scope"].split()
            or claims["sub"] == config.client_id
        ):
            raise _unauthorized()
        return config.issuer, claims["sub"]
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise _unauthorized() from exc


def get_current_principal(
    identity: Annotated[tuple[str, str], Depends(verify_access_token)],
    db: Annotated[Connection, Depends(get_connection, scope="function")],
) -> str:
    issuer, subject = identity
    if issuer == AGENT_TOKEN_ISSUER:
        agent = db.execute(
            text(
                "SELECT a.principal_id FROM agent_credentials c "
                "JOIN agents a ON a.principal_id=c.agent_id "
                "JOIN principals p ON p.id=a.principal_id AND p.kind='agent' "
                "WHERE c.token_hash=:digest AND c.revoked_at IS NULL AND c.expires_at > CURRENT_TIMESTAMP"
            ),
            {"digest": subject},
        ).scalar_one_or_none()
        if agent is None:
            raise _unauthorized()
        return agent
    principal_id = (
        "user:" + hashlib.sha256(f"{issuer}\0{subject}".encode("utf-8")).hexdigest()
    )
    db.execute(
        text(
            "INSERT INTO principals (id, kind, issuer, subject) VALUES (:id, 'user', :issuer, :subject) ON CONFLICT DO NOTHING"
        ),
        {"id": principal_id, "issuer": issuer, "subject": subject},
    )
    row = (
        db.execute(
            text(
                "SELECT id, kind FROM principals WHERE issuer = :issuer AND subject = :subject"
            ),
            {"issuer": issuer, "subject": subject},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["kind"] != "user":
        raise _unauthorized()
    return row["id"]


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/config")
def public_auth_config():
    config = oidc_config()
    if config is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "issuer": config.issuer,
        "clientId": config.client_id,
        "audience": config.audience,
    }


@router.get("/me")
def current_user(principal: Annotated[str, Depends(get_current_principal)]):
    return {
        "id": principal,
        "kind": "agent" if principal.startswith("agent:") else "user",
    }
