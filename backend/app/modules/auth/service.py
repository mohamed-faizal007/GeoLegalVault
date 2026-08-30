"""auth module service layer — login, refresh rotation, logout.

Rate limiting is an in-memory per-process stub (fine for the single-instance
prototype target; a distributed deployment would need a shared store like
Redis instead).
"""

import logging
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from app.modules.audit import service as audit
from app.modules.auth import models as sessions
from app.modules.users import service as users_service

_logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 5
_WINDOW_SEC = 60.0
_failed_attempts: dict[str, list[float]] = defaultdict(list)


class InvalidCredentials(Exception):
    pass


class AccountDisabled(Exception):
    pass


class RateLimited(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass


def _check_rate_limit(email: str) -> None:
    now = time.monotonic()
    attempts = [t for t in _failed_attempts[email] if now - t < _WINDOW_SEC]
    _failed_attempts[email] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        raise RateLimited(email)


def _record_failure(email: str) -> None:
    _failed_attempts[email].append(time.monotonic())


def _reset_failures(email: str) -> None:
    _failed_attempts.pop(email, None)


async def _issue_session(db: AsyncIOMotorDatabase, user: dict) -> tuple[str, str]:
    """Create a fresh refresh-token family and return (access, refresh)."""
    user_id = str(user["_id"])
    role = user["role"]
    family = str(uuid.uuid4())
    jti = str(uuid.uuid4())

    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    await sessions.insert_session(
        db, jti=jti, family=family, user_id=user_id, expires_at=expires_at
    )

    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id, role, family=family, jti=jti)
    return access_token, refresh_token


async def login(
    db: AsyncIOMotorDatabase, email: str, password: str, *, ip: str | None = None
) -> tuple[dict, str, str]:
    """Returns (user_doc, access_token, refresh_token). Raises on failure."""
    email = email.lower()
    try:
        _check_rate_limit(email)
    except RateLimited:
        _logger.warning("auth: login rate-limited", extra={"email": email, "ip": ip})
        await audit.record(
            actor_id=email,
            action="LOGIN_FAILURE",
            target_type="user",
            target_id=email,
            result="RATE_LIMITED",
            ip=ip,
        )
        raise

    user = await users_service.get_user_by_email(db, email)
    if user is None or not verify_password(password, user["password_hash"]):
        _record_failure(email)
        _logger.warning("auth: login failed", extra={"email": email, "ip": ip})
        await audit.record(
            actor_id=email,
            action="LOGIN_FAILURE",
            target_type="user",
            target_id=email,
            result="INVALID_CREDENTIALS",
            ip=ip,
        )
        raise InvalidCredentials(email)

    if not user.get("is_active", False):
        _logger.warning("auth: login rejected — account disabled", extra={"email": email, "ip": ip})
        await audit.record(
            actor_id=user["_id"],
            action="LOGIN_FAILURE",
            target_type="user",
            target_id=user["_id"],
            result="ACCOUNT_DISABLED",
            ip=ip,
        )
        raise AccountDisabled(email)

    _reset_failures(email)
    await users_service.record_login(db, user["_id"])

    access_token, refresh_token = await _issue_session(db, user)
    await audit.record(
        actor_id=user["_id"],
        action="LOGIN_SUCCESS",
        target_type="user",
        target_id=user["_id"],
        result="SUCCESS",
        ip=ip,
    )
    return user, access_token, refresh_token


async def refresh(db: AsyncIOMotorDatabase, refresh_token: str) -> tuple[str, str]:
    """Rotate a refresh token. Returns (new_access_token, new_refresh_token).

    Detects reuse of an already-rotated token and revokes the whole family.
    """
    try:
        decoded = verify_token(refresh_token, expected_type=TokenType.REFRESH)
    except TokenError as exc:
        raise InvalidRefreshToken(str(exc)) from exc

    session = await sessions.get_session(db, decoded.jti)
    if session is None:
        raise InvalidRefreshToken("unknown session")

    if session["revoked"]:
        raise InvalidRefreshToken("session revoked")

    if session["replaced_by"] is not None:
        # This token was already used once to rotate — reuse detected.
        await sessions.revoke_family(db, session["family"])
        raise InvalidRefreshToken("refresh token reuse detected; session family revoked")

    user = await users_service.get_user_by_id(db, decoded.sub)
    if user is None or not user.get("is_active", False):
        await sessions.revoke_family(db, session["family"])
        raise InvalidRefreshToken("user no longer active")

    new_jti = str(uuid.uuid4())
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    await sessions.insert_session(
        db, jti=new_jti, family=session["family"], user_id=decoded.sub, expires_at=expires_at
    )
    await sessions.mark_replaced(db, decoded.jti, new_jti)

    access_token = create_access_token(decoded.sub, user["role"])
    new_refresh_token = create_refresh_token(
        decoded.sub, user["role"], family=session["family"], jti=new_jti
    )
    return access_token, new_refresh_token


async def logout(db: AsyncIOMotorDatabase, refresh_token: str) -> None:
    """Best-effort: revoke the session tied to this refresh token, if any."""
    try:
        decoded = verify_token(refresh_token, expected_type=TokenType.REFRESH)
    except TokenError:
        return
    await sessions.revoke_session(db, decoded.jti)
