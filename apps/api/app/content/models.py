"""Content entities: items, attachments, tags, categories, reviews."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        sa.UniqueConstraint("author_id", "slug"),
        sa.Index("ix_items_state_published_at", "state", "published_at"),
        sa.Index("ix_items_author_type", "author_id", "type", "published_at"),
        sa.Index("ix_items_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    author_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(
        sa.Enum("video", "article", "teaching_material", name="item_type"), nullable=False
    )
    video_kind: Mapped[str | None] = mapped_column(
        sa.Enum("hosted", "embed", "live", name="video_kind")
    )
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text())
    body_md: Mapped[str | None] = mapped_column(sa.Text())
    body_html_cached: Mapped[str | None] = mapped_column(sa.Text())
    external_url: Mapped[str | None] = mapped_column(sa.Text())
    license: Mapped[str] = mapped_column(
        sa.Enum(
            "cc-by-4.0", "cc-by-sa-4.0", "cc-by-nc-4.0", "cc0-1.0", "arr",
            name="content_license",
        ),
        nullable=False,
        default="cc-by-4.0",
    )
    paywall_config_id: Mapped[str | None] = mapped_column(sa.String(26))
    state: Mapped[str] = mapped_column(
        sa.Enum("draft", "pending_review", "published", "tombstoned", name="item_state"),
        nullable=False,
        default="draft",
    )
    published_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR())


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    owner_user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    item_id: Mapped[str | None] = mapped_column(sa.String(26), sa.ForeignKey("items.id"))
    role: Mapped[str] = mapped_column(
        sa.Enum(
            "video_primary",
            "video_thumbnail",
            "video_transcoded",
            "article_attachment",
            "teaching_material_file",
            "profile_photo",
            "certificate_pdf",
            "data_export_zip",
            name="attachment_role",
        ),
        nullable=False,
    )
    r2_key: Mapped[str] = mapped_column(sa.Text(), unique=True, nullable=False)
    bytes: Mapped[int | None] = mapped_column(sa.BigInteger())
    mime: Mapped[str | None] = mapped_column(sa.Text())
    checksum_sha256: Mapped[bytes | None] = mapped_column(sa.LargeBinary())
    state: Mapped[str] = mapped_column(
        sa.Enum("uploading", "scanning", "clean", "quarantined", "deleted", name="attachment_state"),
        nullable=False,
        default="uploading",
    )
    scanned_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    name: Mapped[str] = mapped_column(sa.Text(), unique=True, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    slug: Mapped[str] = mapped_column(sa.Text(), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(sa.String(26), sa.ForeignKey("categories.id"))


class ItemTag(Base):
    __tablename__ = "item_tags"

    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ItemCategory(Base):
    __tablename__ = "item_categories"

    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )


class ReviewSubmission(Base):
    __tablename__ = "review_submissions"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    submitted_by: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.Enum("pending", "approved", "rejected", name="review_state"),
        nullable=False,
        default="pending",
    )
    decision_actor_id: Mapped[str | None] = mapped_column(sa.String(26))
    decision_reason: Mapped[str | None] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class SlugReserved(Base):
    __tablename__ = "slug_reserved"

    slug: Mapped[str] = mapped_column(sa.Text(), primary_key=True)


RESERVED_SLUGS = {
    "admin", "api", "c", "verify", "legal", "me", "auth", "assets", "static",
    "well-known", "items", "discover", "search", "workshops", "contributors",
    "csrf", "healthz", "readyz", "metrics", "robots.txt", "sitemap.xml",
    "favicon.ico", "manifest.json",
}
