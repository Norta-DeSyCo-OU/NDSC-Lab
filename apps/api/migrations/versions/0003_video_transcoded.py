"""Add `video_transcoded` to attachment_role enum.

Revision ID: 0003_video_transcoded
Revises: 0002_full_schema
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op


revision = "0003_video_transcoded"
down_revision = "0002_full_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `ALTER TYPE ... ADD VALUE` cannot run inside a transaction block in PG.
    # Alembic wraps each migration in a transaction by default; disable for this op.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE attachment_role ADD VALUE IF NOT EXISTS 'video_transcoded'")


def downgrade() -> None:
    # Postgres enum values cannot be removed without recreating the type.
    # Leaving as a no-op; a future cleanup migration can rebuild the enum.
    pass
