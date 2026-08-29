import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_password_hash_roundtrip():
    password = "correct horse battery staple"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True


def test_wrong_password_fails():
    hashed = hash_password("the-real-password")
    assert verify_password("not-the-real-password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token("user-123", "ADMINISTRATOR")
    decoded = verify_token(token, expected_type=TokenType.ACCESS)

    assert decoded.sub == "user-123"
    assert decoded.role == "ADMINISTRATOR"
    assert decoded.token_type == TokenType.ACCESS


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-123", "AUDITOR", family="fam-1")
    decoded = verify_token(token, expected_type=TokenType.REFRESH)

    assert decoded.sub == "user-123"
    assert decoded.family == "fam-1"


def test_wrong_expected_type_rejected():
    access = create_access_token("user-123", "AUDITOR")
    with pytest.raises(TokenError):
        verify_token(access, expected_type=TokenType.REFRESH)


def test_expired_token_rejected():
    settings = get_settings()
    now = datetime.now(UTC)
    expired_payload = {
        "sub": "user-123",
        "role": "AUDITOR",
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=1),
        "jti": "some-jti",
        "type": TokenType.ACCESS,
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET, algorithm="HS256")

    with pytest.raises(TokenError):
        verify_token(expired_token, expected_type=TokenType.ACCESS)


def test_tampered_token_rejected():
    token = create_access_token("user-123", "AUDITOR")
    header, payload, signature = token.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    tampered_token = f"{header}.{payload}.{tampered_signature}"

    with pytest.raises(TokenError):
        verify_token(tampered_token, expected_type=TokenType.ACCESS)


def test_alg_none_token_rejected():
    header_json = json.dumps({"alg": "none", "typ": "JWT"}).encode()
    header = base64.urlsafe_b64encode(header_json).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "sub": "user-123",
                "role": "ADMINISTRATOR",
                "jti": "x",
                "type": TokenType.ACCESS,
                "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
            }
        ).encode()
    ).rstrip(b"=")
    none_alg_token = f"{header.decode()}.{payload.decode()}."

    with pytest.raises(TokenError):
        verify_token(none_alg_token, expected_type=TokenType.ACCESS)
