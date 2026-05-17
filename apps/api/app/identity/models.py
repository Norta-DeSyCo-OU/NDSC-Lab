"""Identity & access entities."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    display_name: Mapped[str | None] = mapped_column(sa.Text())
    role: Mapped[str] = mapped_column(
        sa.Enum("user", "contributor", "admin", name="user_role"),
        default="user",
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        sa.Enum(
            "pending_verify", "active", "banned", "deleted",
            name="user_state",
        ),
        default="pending_verify",
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(sa.Text())
    password_changed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    mfa_secret: Mapped[bytes | None] = mapped_column(sa.LargeBinary())  # FR-AUTH-009
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    age_confirmed_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    tos_version: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    cookie_consent_version: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(sa.String(26))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class OAuthIdentity(Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (sa.UniqueConstraint("provider", "subject"),)

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        sa.Enum("google", name="oauth_provider"), nullable=False
    )
    subject: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    email_lower: Mapped[str] = mapped_column(CITEXT(), nullable=False, index=True)
    ip: Mapped[Any] = mapped_column(INET())
    success: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )


class RoleTransition(Base):
    __tablename__ = "role_transitions"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    from_role: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    to_role: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(sa.String(26))
    reason: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )


class ContributorApplication(Base):
    __tablename__ = "contributor_applications"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    motivation: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    links: Mapped[dict[str, Any] | None] = mapped_column(JSONB())
    state: Mapped[str] = mapped_column(
        sa.Enum("pending", "approved", "rejected", "withdrawn", name="contributor_app_state"),
        default="pending",
        nullable=False,
    )
    decision_actor_id: Mapped[str | None] = mapped_column(sa.String(26))
    decision_reason: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class TosAcceptance(Base):
    __tablename__ = "tos_acceptances"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tos_version: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    ip: Mapped[Any | None] = mapped_column(INET())


class CookieConsent(Base):
    __tablename__ = "cookie_consents"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str | None] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE")
    )
    anon_id: Mapped[str | None] = mapped_column(sa.Text())
    essential: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    analytics: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    version: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
