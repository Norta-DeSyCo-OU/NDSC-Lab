"""Curation entities: profiles, sections, collections, courses, workshops."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base
from app.core.types import new_ulid


class ContributorProfile(Base):
    __tablename__ = "contributor_profiles"

    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    bio_md: Mapped[str | None] = mapped_column(sa.Text())
    photo_attachment_id: Mapped[str | None] = mapped_column(sa.String(26))
    affiliation: Mapped[str | None] = mapped_column(sa.Text())
    orcid: Mapped[str | None] = mapped_column(sa.Text())
    links: Mapped[Any | None] = mapped_column(JSONB())
    contacts: Mapped[Any | None] = mapped_column(JSONB())
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )


class ProfileSection(Base):
    __tablename__ = "profile_sections"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    profile_user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("contributor_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    parent_section_id: Mapped[str | None] = mapped_column(
        sa.String(26), sa.ForeignKey("profile_sections.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_md: Mapped[str | None] = mapped_column(sa.Text())


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (sa.UniqueConstraint("owner_user_id", "slug"),)

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    owner_user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    description_md: Mapped[str | None] = mapped_column(sa.Text())
    cover_attachment_id: Mapped[str | None] = mapped_column(sa.String(26))
    is_course: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    is_required_for_course: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)


class CourseCompletionCriterion(Base):
    __tablename__ = "course_completion_criteria"

    collection_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    rule: Mapped[Any] = mapped_column(JSONB(), nullable=False)


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"

    user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    collection_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(
        sa.Enum("in_progress", "completed", name="user_course_progress_state"),
        nullable=False,
        default="in_progress",
    )
    progress: Mapped[Any | None] = mapped_column(JSONB())
    completed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text(), unique=True, nullable=False)
    abstract_md: Mapped[str | None] = mapped_column(sa.Text())
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(sa.Text())
    is_online: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    registration_url: Mapped[str | None] = mapped_column(sa.Text())
    recording_item_id: Mapped[str | None] = mapped_column(sa.String(26))
    state: Mapped[str] = mapped_column(
        sa.Enum("draft", "pending_review", "published", "tombstoned", name="workshop_state"),
        nullable=False,
        default="draft",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )


class WorkshopSpeaker(Base):
    __tablename__ = "workshop_speakers"

    workshop_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("workshops.id", ondelete="CASCADE"), primary_key=True
    )
    contributor_user_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)


class CertCompletionSuggestion(Base):
    __tablename__ = "cert_completion_suggestions"

    id: Mapped[str] = mapped_column(sa.String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(sa.String(26), sa.ForeignKey("users.id"), nullable=False)
    collection_id: Mapped[str] = mapped_column(
        sa.String(26), sa.ForeignKey("collections.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )
    state: Mapped[str] = mapped_column(
        sa.Enum("open", "issued", "dismissed", name="cert_suggestion_state"),
        nullable=False,
        default="open",
    )
