"""Certification entities."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class SigningKey(Base):
    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    key_id: Mapped[str] = mapped_column(sa.Text(), unique=True, nullable=False)
    algo: Mapped[str] = mapped_column(sa.Text(), nullable=False, default="ed25519")
    public_key_pem: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    private_key_ref: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("active", "retired", name="signing_key_state"),
        nullable=False,
        default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    collection_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    issued_by_admin_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    signing_key_id: Mapped[str] = mapped_column(
        sa.Text(), sa.ForeignKey("signing_keys.key_id"), nullable=False
    )
    signature_b64: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    pdf_attachment_id: Mapped[str | None] = mapped_column(sa.String(26))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(sa.Text())


class CertAdminPseudonym(Base):
    """Mapping for D-13: when an issuing admin is erased, their identity is redacted."""

    __tablename__ = "cert_admin_pseudonyms"

    original_admin_id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    pseudonym_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    redacted_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
