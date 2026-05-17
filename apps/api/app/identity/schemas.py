"""Pydantic schemas for identity endpoints."""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN = 12
_PASSWORD_RE = re.compile(r"^[\x21-\x7E ]{12,256}$")  # printable ASCII + space, 12-256


class SignupIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=PASSWORD_MIN, max_length=256)]
    age_confirmed: bool
    tos_version: str
    cookie_consent_version: str
    analytics_opt_in: bool = False

    @field_validator("password")
    @classmethod
    def _pwd_charset(cls, v: str) -> str:
        if not _PASSWORD_RE.match(v):
            raise ValueError("invalid_password_charset")
        return v

    @field_validator("age_confirmed")
    @classmethod
    def _age(cls, v: bool) -> bool:
        if not v:
            raise ValueError("age_not_confirmed")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: Annotated[str, Field(min_length=PASSWORD_MIN, max_length=256)]

    @field_validator("password")
    @classmethod
    def _pwd_charset(cls, v: str) -> str:
        if not _PASSWORD_RE.match(v):
            raise ValueError("invalid_password_charset")
        return v


class GenericOK(BaseModel):
    ok: bool = True


class MeOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    state: str
    display_name: str | None
    photo_url: str | None = None
    profile_slug: str | None = None
