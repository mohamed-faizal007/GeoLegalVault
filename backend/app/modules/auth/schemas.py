"""auth module Pydantic schemas."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_min: int
