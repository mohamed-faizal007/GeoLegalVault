"""users module Pydantic schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.users.models import Role

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    if not _EMAIL_RE.match(value):
        raise ValueError("invalid email address")
    return value.lower()


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    role: Role
    assigned_geofence_ids: list[str] = Field(default_factory=list)

    _normalize_email = field_validator("email")(_validate_email)


class UserUpdate(BaseModel):
    """All fields optional; only provided fields are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    assigned_geofence_ids: list[str] | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    assigned_geofence_ids: list[str]
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None


class UserListOut(BaseModel):
    items: list[UserOut]
    page: int
    limit: int
    total: int
