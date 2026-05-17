"""Add `contacts` JSONB column to contributor_profiles.

Revision ID: 0004_profile_contacts
Revises: 0003_video_transcoded
Create Date: 2026-05-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0004_profile_contacts"
down_revision = "0003_video_transcoded"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contributor_profiles",
        sa.Column("contacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contributor_profiles", "contacts")
