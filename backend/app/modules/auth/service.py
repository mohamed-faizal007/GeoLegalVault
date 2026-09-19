"""auth module service layer — login, refresh rotation, logout.

Login rate limiting is backed by a MongoDB collection (login_rate_limits),
not in-process memory, so the 5-attempts/60s lockout is shared across every
backend instance/pod rather than being bypassable by hitting a different one.
"""

import logging
import uuid
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
_RATE_LIMIT_COLLECTION = "login_rate_limits"


class InvalidCredentials(Exception):
    pass


class AccountDisabled(Exception):
    pass


class RateLimited(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass


async def _check_rate_limit(db: AsyncIOMotorDatabase, email: str) -> None:
    doc = await db[_RATE_LIMIT_COLLECTION].find_one({"_id": email})
    if doc is None:
        return
    now = datetime.now(UTC)
    # Motor/BSON hands back a naive datetime (UTC) by default; normalize
    # before comparing against the aware `now` to avoid a TypeError.
    stored_expiry = doc["expires_at"]
    if stored_expiry.tzinfo is None:
        stored_expiry = stored_expiry.replace(tzinfo=UTC)
    if stored_expiry > now and doc["count"] >= _MAX_ATTEMPTS:
        raise RateLimited(email)


async def _record_failure(db: AsyncIOMotorDatabase, email: str) -> None:
    """Atomic INCR-with-expiry: within an active window, increments the
    counter; once the window has lapsed, starts a fresh one. The single
    find_one_and_update pipeline avoids a read-modify-write race between
    concurrent requests for the same email (across processes/instances)."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=_WINDOW_SEC)
    await db[_RATE_LIMIT_COLLECTION].find_one_and_update(
        {"_id": email},
        [
            {
                "$set": {
                    "count": {
                        "$cond": [
                            {"$gt": ["$expires_at", now]},
                            {"$add": ["$count", 1]},
                            1,
                        ]
                    },
                    "expires_at": {
                        "$cond": [
                            {"$gt": ["$expires_at", now]},
                            "$expires_at",
                            expires_at,
                        ]
                    },
                }
            }
        ],
        upsert=True,
    )


async def _reset_failures(db: AsyncIOMotorDatabase, email: str) -> None:
    await db[_RATE_LIMIT_COLLECTION].delete_one({"_id": email})


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
        await _check_rate_limit(db, email)
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
        await _record_failure(db, email)
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

    await _reset_failures(db, email)
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
