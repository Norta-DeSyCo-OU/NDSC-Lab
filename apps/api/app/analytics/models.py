"""Analytics entities: raw events + daily aggregates."""
from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base


class RawViewEvent(Base):
    __tablename__ = "raw_view_events"
    __table_args__ = (
        sa.Index("ix_rve_item_ts", "item_id", "qualifying_ts"),
        sa.Index("ix_rve_contrib_ts", "contributor_user_id", "qualifying_ts"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("items.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    category_id: Mapped[str | None] = mapped_column(sa.String(26))
    contributor_user_id: Mapped[str] = mapped_column(sa.String(26), nullable=False)
    view_session_uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    qualifying_ts: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    data: Mapped[Any | None] = mapped_column(JSONB())


class DailyItemAggregate(Base):
    __tablename__ = "daily_item_aggregates"

    day: Mapped[date_cls] = mapped_column(sa.Date(), primary_key=True)
    item_id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    views: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)


class DailyContributorAggregate(Base):
    __tablename__ = "daily_contributor_aggregates"

    day: Mapped[date_cls] = mapped_column(sa.Date(), primary_key=True)
    contributor_user_id: Mapped[str] = mapped_column(sa.String(26), primary_key=True)
    views: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
