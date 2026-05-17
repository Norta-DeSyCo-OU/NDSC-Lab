"""Legal entities: takedowns, erasure, data exports, ToS, settings."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class LegalDocument(Base):
    __tablename__ = "legal_documents"
    __table_args__ = (sa.UniqueConstraint("kind", "version"),)

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    kind: Mapped[str] = mapped_column(
        sa.Enum("tos", "privacy", name="legal_kind"), nullable=False
    )
    version: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    body_md: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    material_change: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)


class TakedownRequest(Base):
    __tablename__ = "takedown_requests"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    complainant_name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    complainant_email: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    complainant_address: Mapped[str | None] = mapped_column(sa.Text())
    target_url: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    target_item_id: Mapped[str | None] = mapped_column(sa.String(26))
    sworn_statement: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("open", "closed_tombstoned", "closed_rejected", name="takedown_state"),
        nullable=False,
        default="open",
    )
    decision_actor_id: Mapped[str | None] = mapped_column(sa.String(26))
    decision_reason: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class ErasureRequest(Base):
    __tablename__ = "erasure_requests"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("pending", "executing", "completed", "cancelled", name="erasure_state"),
        nullable=False,
        default="pending",
    )
    eta_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    grace_until: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class DataExportRequest(Base):
    __tablename__ = "data_export_requests"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("pending", "building", "ready", "expired", name="data_export_state"),
        nullable=False,
        default="pending",
    )
    zip_attachment_id: Mapped[str | None] = mapped_column(sa.String(26))
    presigned_url_expires_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    built_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(sa.Text(), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB(), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(sa.String(26))
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )


class ContributorTunable(Base):
    __tablename__ = "contributor_tunables"

    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    storage_quota_bytes: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False, default=20 * 2**30)
    hosted_video_allowed: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    embed_only: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    max_video_duration_s: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=4 * 3600)
    updated_by: Mapped[str | None] = mapped_column(sa.String(26))
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
