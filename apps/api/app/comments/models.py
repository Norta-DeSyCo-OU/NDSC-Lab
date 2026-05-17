"""Comment entities."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        sa.Index("ix_comments_item_ts", "item_id", "created_at"),
        sa.Index("ix_comments_author_ts", "author_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    item_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(sa.String(26), sa.ForeignKey("comments.id", ondelete="CASCADE"))
    body_md: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("visible", "deleted", "hidden_by_admin", name="comment_state"),
        nullable=False,
        default="visible",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class CommentReport(Base):
    __tablename__ = "comment_reports"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    comment_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("comments.id"), nullable=False)
    reporter_id: Mapped[str | None] = mapped_column(sa.String(26), sa.ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("open", "closed", "actioned", name="comment_report_state"),
        nullable=False,
        default="open",
    )
    decided_by: Mapped[str | None] = mapped_column(sa.String(26))
    decided_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
