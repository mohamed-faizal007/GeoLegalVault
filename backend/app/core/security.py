"""Password hashing (Argon2id) and JWT creation/verification.

JWT algorithm is pinned to HS256 on both encode and decode. PyJWT's
`algorithms=` allow-list on decode is what actually rejects `alg=none` and
any other algorithm — it does not fall back to the token's own header.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class DecodedToken:
    sub: str
    role: str
    jti: str
    token_type: TokenType
    family: str | None = None


class TokenError(Exception):
    """Any invalid/expired/malformed/wrong-algorithm token."""


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
        "jti": str(uuid.uuid4()),
        "type": TokenType.ACCESS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, role: str, family: str, jti: str | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        "jti": jti or str(uuid.uuid4()),
        "type": TokenType.REFRESH,
        "family": family,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str, expected_type: TokenType) -> DecodedToken:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"expected a {expected_type} token")

    try:
        return DecodedToken(
            sub=payload["sub"],
            role=payload["role"],
            jti=payload["jti"],
            token_type=TokenType(payload["type"]),
            family=payload.get("family"),
        )
    except KeyError as exc:
        raise TokenError(f"missing claim: {exc}") from exc
