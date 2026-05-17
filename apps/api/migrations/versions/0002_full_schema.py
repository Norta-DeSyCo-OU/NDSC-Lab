"""Add remaining schema for content, curation, comments, analytics, legal.

Revision ID: 0002_full_schema
Revises: 0001_init
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_full_schema"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # items
    op.create_table(
        "items",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("author_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "type",
            sa.Enum("video", "article", "teaching_material", name="item_type"),
            nullable=False,
        ),
        sa.Column("video_kind", sa.Enum("hosted", "embed", "live", name="video_kind")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("body_md", sa.Text()),
        sa.Column("body_html_cached", sa.Text()),
        sa.Column("external_url", sa.Text()),
        sa.Column(
            "license",
            sa.Enum(
                "cc-by-4.0", "cc-by-sa-4.0", "cc-by-nc-4.0", "cc0-1.0", "arr",
                name="content_license",
            ),
            nullable=False,
            server_default="cc-by-4.0",
        ),
        sa.Column("paywall_config_id", sa.String(26)),
        sa.Column(
            "state",
            sa.Enum("draft", "pending_review", "published", "tombstoned", name="item_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.UniqueConstraint("author_id", "slug"),
    )
    op.execute(
        "CREATE INDEX ix_items_search ON items USING GIN (search_vector)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_item_search_vector() RETURNS trigger AS $$
        BEGIN
          NEW.search_vector :=
            setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(NEW.summary, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(NEW.body_md, '')), 'C');
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER items_search_vector_update BEFORE INSERT OR UPDATE ON items "
        "FOR EACH ROW EXECUTE FUNCTION update_item_search_vector();"
    )
    op.create_index("ix_items_state_published_at", "items", ["state", "published_at"])
    op.create_index("ix_items_author_type", "items", ["author_id", "type", "published_at"])

    # attachments
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("owner_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id")),
        sa.Column(
            "role",
            sa.Enum(
                "video_primary", "video_thumbnail", "article_attachment", "teaching_material_file",
                "profile_photo", "certificate_pdf", "data_export_zip",
                name="attachment_role",
            ),
            nullable=False,
        ),
        sa.Column("r2_key", sa.Text(), nullable=False, unique=True),
        sa.Column("bytes", sa.BigInteger()),
        sa.Column("mime", sa.Text()),
        sa.Column("checksum_sha256", sa.LargeBinary()),
        sa.Column(
            "state",
            sa.Enum("uploading", "scanning", "clean", "quarantined", "deleted", name="attachment_state"),
            nullable=False,
            server_default="uploading",
        ),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # tags + categories
    op.create_table(
        "tags",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("slug", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.String(26), sa.ForeignKey("categories.id")),
    )
    op.create_table(
        "item_tags",
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(26), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "item_categories",
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.String(26), sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    )

    # review submissions
    op.create_table(
        "review_submissions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "state",
            sa.Enum("pending", "approved", "rejected", name="review_state"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("decision_actor_id", sa.String(26)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
    )

    # slug_reserved
    op.create_table(
        "slug_reserved",
        sa.Column("slug", sa.Text(), primary_key=True),
    )

    # curation
    op.create_table(
        "contributor_profiles",
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slug", postgresql.CITEXT(), unique=True, nullable=False),
        sa.Column("bio_md", sa.Text()),
        sa.Column("photo_attachment_id", sa.String(26)),
        sa.Column("affiliation", sa.Text()),
        sa.Column("orcid", sa.Text()),
        sa.Column("links", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "profile_sections",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "profile_user_id",
            sa.String(26),
            sa.ForeignKey("contributor_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_section_id",
            sa.String(26),
            sa.ForeignKey("profile_sections.id", ondelete="CASCADE"),
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body_md", sa.Text()),
    )
    op.create_table(
        "collections",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("owner_user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description_md", sa.Text()),
        sa.Column("cover_attachment_id", sa.String(26)),
        sa.Column("is_course", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_user_id", "slug"),
    )
    op.create_table(
        "collection_items",
        sa.Column("collection_id", sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_required_for_course", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "course_completion_criteria",
        sa.Column("collection_id", sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rule", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "user_course_progress",
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collection_id", sa.String(26), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "state",
            sa.Enum("in_progress", "completed", name="user_course_progress_state"),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("progress", postgresql.JSONB()),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_table(
        "workshops",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), unique=True, nullable=False),
        sa.Column("abstract_md", sa.Text()),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("registration_url", sa.Text()),
        sa.Column("recording_item_id", sa.String(26)),
        sa.Column(
            "state",
            sa.Enum("draft", "pending_review", "published", "tombstoned", name="workshop_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "workshop_speakers",
        sa.Column("workshop_id", sa.String(26), sa.ForeignKey("workshops.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("contributor_user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "cert_completion_suggestions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("collection_id", sa.String(26), sa.ForeignKey("collections.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "state",
            sa.Enum("open", "issued", "dismissed", name="cert_suggestion_state"),
            nullable=False,
            server_default="open",
        ),
    )

    # comments
    op.create_table(
        "comments",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", sa.String(26), sa.ForeignKey("comments.id", ondelete="CASCADE")),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column(
            "state",
            sa.Enum("visible", "deleted", "hidden_by_admin", name="comment_state"),
            nullable=False,
            server_default="visible",
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_comments_item_ts", "comments", ["item_id", "created_at"])
    op.create_index("ix_comments_author_ts", "comments", ["author_id", "created_at"])

    op.create_table(
        "comment_reports",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("comment_id", sa.String(26), sa.ForeignKey("comments.id"), nullable=False),
        sa.Column("reporter_id", sa.String(26), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "state",
            sa.Enum("open", "closed", "actioned", name="comment_report_state"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("decided_by", sa.String(26)),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
    )

    # analytics
    op.create_table(
        "raw_view_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_id", sa.String(26), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("category_id", sa.String(26)),
        sa.Column("contributor_user_id", sa.String(26), nullable=False),
        sa.Column("view_session_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qualifying_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("data", postgresql.JSONB()),
    )
    op.create_index("ix_rve_item_ts", "raw_view_events", ["item_id", "qualifying_ts"])
    op.create_index("ix_rve_contrib_ts", "raw_view_events", ["contributor_user_id", "qualifying_ts"])

    op.create_table(
        "daily_item_aggregates",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("item_id", sa.String(26), primary_key=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "daily_contributor_aggregates",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("contributor_user_id", sa.String(26), primary_key=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
    )

    # legal + settings
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("kind", sa.Enum("tos", "privacy", name="legal_kind"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("material_change", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("kind", "version"),
    )
    op.create_table(
        "takedown_requests",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("complainant_name", sa.Text(), nullable=False),
        sa.Column("complainant_email", sa.Text(), nullable=False),
        sa.Column("complainant_address", sa.Text()),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("target_item_id", sa.String(26)),
        sa.Column("sworn_statement", sa.Text(), nullable=False),
        sa.Column(
            "state",
            sa.Enum("open", "closed_tombstoned", "closed_rejected", name="takedown_state"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("decision_actor_id", sa.String(26)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_table(
        "erasure_requests",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "state",
            sa.Enum("pending", "executing", "completed", "cancelled", name="erasure_state"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("eta_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("grace_until", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_table(
        "data_export_requests",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "state",
            sa.Enum("pending", "building", "ready", "expired", name="data_export_state"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("zip_attachment_id", sa.String(26)),
        sa.Column("presigned_url_expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("built_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "platform_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.String(26)),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "contributor_tunables",
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=False, server_default="21474836480"),
        sa.Column("hosted_video_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("embed_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_video_duration_s", sa.Integer(), nullable=False, server_default="14400"),
        sa.Column("updated_by", sa.String(26)),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # D-15 canonical projection: implemented in application code (app/core/audit.py:_canon)
    # rather than as a Postgres GENERATED column. `extract(epoch from <timestamptz>)`
    # is not IMMUTABLE in Postgres so it cannot be used in a STORED generated column.
    # The HMAC chain integrity is preserved either way; offline SQL-side verification
    # would require an IMMUTABLE rewrite (e.g., to_timestamp arithmetic) — deferred.

    # Seed reserved slugs.
    op.execute(
        "INSERT INTO slug_reserved (slug) VALUES "
        "('admin'),('api'),('c'),('verify'),('legal'),('me'),('auth'),"
        "('assets'),('static'),('well-known'),('items'),('discover'),"
        "('search'),('workshops'),('contributors'),('csrf'),('healthz'),"
        "('readyz'),('metrics');"
    )


def downgrade() -> None:
    for t in [
        "contributor_tunables", "platform_settings", "data_export_requests",
        "erasure_requests", "takedown_requests", "legal_documents",
        "daily_contributor_aggregates", "daily_item_aggregates", "raw_view_events",
        "comment_reports", "comments",
        "cert_completion_suggestions",
        "workshop_speakers", "workshops",
        "user_course_progress", "course_completion_criteria",
        "collection_items", "collections",
        "profile_sections", "contributor_profiles",
        "slug_reserved", "review_submissions",
        "item_categories", "item_tags", "categories", "tags",
        "attachments", "items",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
    for e in [
        "data_export_state", "erasure_state", "takedown_state", "legal_kind",
        "comment_report_state", "comment_state",
        "cert_suggestion_state", "workshop_state",
        "user_course_progress_state",
        "review_state", "attachment_state", "attachment_role",
        "item_state", "content_license", "video_kind", "item_type",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {e};")
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS canon;")
