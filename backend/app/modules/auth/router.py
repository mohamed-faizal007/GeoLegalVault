"""auth module router — login, refresh, logout."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import CurrentUser
from app.modules.auth import service
from app.modules.auth.schemas import AccessTokenResponse, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.JWT_REFRESH_TTL_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> AccessTokenResponse:
    settings = get_settings()
    ip = request.client.host if request.client else None
    try:
        _user, access_token, refresh_token = await service.login(
            db, payload.email, payload.password, ip=ip
        )
    except (service.InvalidCredentials, service.AccountDisabled, service.RateLimited) as exc:
        # Same generic message for all failure modes: no user enumeration.
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if isinstance(exc, service.RateLimited)
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code, detail="Invalid email or password") from exc

    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(
        access_token=access_token, expires_in_min=settings.JWT_ACCESS_TTL_MIN
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE_NAME)] = None,
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    settings = get_settings()
    try:
        access_token, new_refresh_token = await service.refresh(db, refresh_token)
    except service.InvalidRefreshToken as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    _set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(
        access_token=access_token, expires_in_min=settings.JWT_ACCESS_TTL_MIN
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    _current_user: CurrentUser,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE_NAME)] = None,
) -> None:
    if refresh_token is not None:
        await service.logout(db, refresh_token)
    _clear_refresh_cookie(response)
