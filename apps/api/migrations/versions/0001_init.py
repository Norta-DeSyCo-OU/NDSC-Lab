"""Initial schema.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("email_verified_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("display_name", sa.Text()),
        sa.Column(
            "role",
            sa.Enum("user", "contributor", "admin", name="user_role"),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "state",
            sa.Enum(
                "pending_verify", "active", "banned", "deleted",
                name="user_state",
            ),
            nullable=False,
            server_default="pending_verify",
        ),
        sa.Column("password_hash", sa.Text()),
        sa.Column("password_changed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("mfa_secret", sa.LargeBinary()),
        sa.Column("mfa_enabled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("age_confirmed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("tos_version", sa.Text(), nullable=False),
        sa.Column("cookie_consent_version", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.String(26)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Enum("google", name="oauth_provider"), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("provider", "subject"),
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email_lower", postgresql.CITEXT(), nullable=False, index=True),
        sa.Column("ip", postgresql.INET()),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_login_attempts_email_ts",
        "login_attempts",
        ["email_lower", "created_at"],
    )

    op.create_table(
        "role_transitions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("from_role", sa.Text(), nullable=False),
        sa.Column("to_role", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(26)),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "contributor_applications",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("motivation", sa.Text(), nullable=False),
        sa.Column("links", postgresql.JSONB()),
        sa.Column(
            "state",
            sa.Enum(
                "pending", "approved", "rejected", "withdrawn",
                name="contributor_app_state",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("decision_actor_id", sa.String(26)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "tos_acceptances",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("tos_version", sa.Text(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ip", postgresql.INET()),
    )

    op.create_table(
        "cookie_consents",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("anon_id", sa.Text()),
        sa.Column("essential", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("analytics", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor_user_id", sa.String(26)),
        sa.Column("actor_ip", postgresql.INET()),
        sa.Column("actor_ua", sa.Text()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("prev_hmac", sa.LargeBinary()),
        sa.Column("hmac", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_actor_ts", "audit_log", ["actor_user_id", "ts"])
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id", "ts"])

    # signing keys + certificates + admin pseudonyms
    op.create_table(
        "signing_keys",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("key_id", sa.Text(), unique=True, nullable=False),
        sa.Column("algo", sa.Text(), nullable=False, server_default="ed25519"),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("private_key_ref", sa.Text(), nullable=False),
        sa.Column(
            "state",
            sa.Enum("active", "retired", name="signing_key_state"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("retired_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "certificates",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("collection_id", sa.String(26), nullable=False),
        sa.Column("issued_by_admin_id", sa.String(26), nullable=False),
        sa.Column(
            "issued_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "signing_key_id",
            sa.Text(),
            sa.ForeignKey("signing_keys.key_id"),
            nullable=False,
        ),
        sa.Column("signature_b64", sa.Text(), nullable=False),
        sa.Column("pdf_attachment_id", sa.String(26)),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoke_reason", sa.Text()),
    )

    op.create_table(
        "cert_admin_pseudonyms",
        sa.Column("original_admin_id", sa.String(26), primary_key=True),
        sa.Column("pseudonym_id", sa.String(26), nullable=False),
        sa.Column(
            "redacted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    for t in [
        "cert_admin_pseudonyms",
        "certificates",
        "signing_keys",
        "audit_log",
        "cookie_consents",
        "tos_acceptances",
        "contributor_applications",
        "role_transitions",
        "login_attempts",
        "oauth_identities",
        "users",
    ]:
        op.drop_table(t)
    for e in [
        "signing_key_state",
        "contributor_app_state",
        "oauth_provider",
        "user_state",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {e};")
