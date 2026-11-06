"""Identity boundary. Production authentication is introduced by issue #36."""

from fastapi import HTTPException, status


def get_current_principal() -> str:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authenticated identity is not configured",
        headers={"WWW-Authenticate": "Bearer"},
    )
