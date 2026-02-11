"""v2.0 Web - Complete schema with auth, multi-tenant, pipelines

Revision ID: 001_v2_web
Revises:
Create Date: 2026-02-09

Tables:
- users (Firebase Auth sync)
- institutions (multi-tenant)
- institution_credentials (encrypted SEI credentials)
- institution_scrapers (version bindings)
- processes (SEI processes)
- documents (individual documents)
- receipts (electronic receipts)
- document_history (audit trail)
- extraction_tasks (background jobs)
- extraction_schedules (APScheduler config)
- pipeline_requests (self-service onboarding)
- system_configuration (key-value config)

Requires: ParadeDB extension for BM25 indexes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "001_v2_web"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable ParadeDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search;")

    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firebase_uid", sa.String(128), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── institutions ──
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sei_url", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("extra_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── institution_credentials ──
    op.create_table(
        "institution_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("credential_type", sa.String(20), nullable=False, server_default="login"),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── institution_scrapers ──
    op.create_table(
        "institution_scrapers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("scraper_version", sa.String(50), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── processes ──
    op.create_table(
        "processes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("process_number", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("links", JSONB(), nullable=False, server_default="{}"),
        sa.Column("best_current_link", sa.String(500)),
        sa.Column("access_type", sa.String(20)),
        sa.Column("category", sa.String(50)),
        sa.Column("category_status", sa.String(50)),
        sa.Column("unit", sa.String(255)),
        sa.Column("authority", sa.String(255)),
        sa.Column("no_valid_links", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("nickname", sa.String(255)),
        sa.Column("documents_data", JSONB(), nullable=False, server_default="{}"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("extra_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── documents ──
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_number", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(100)),
        sa.Column("status", sa.String(30), server_default="not_downloaded"),
        sa.Column("storage_path", sa.String(500)),
        sa.Column("extra_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── receipts ──
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("signatory", sa.String(255)),
        sa.Column("document_numbers", ARRAY(sa.String()), server_default="{}"),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── document_history ──
    op.create_table(
        "document_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_number", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("old_status", sa.String(50)),
        sa.Column("new_status", sa.String(50)),
        sa.Column("file_path", sa.String(500)),
        sa.Column("file_size", sa.String(50)),
        sa.Column("performed_by", sa.String(255), server_default="system"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("extra_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── extraction_tasks ──
    op.create_table(
        "extraction_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("trigger_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("total_processes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_processes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("result_summary", JSONB(), nullable=False, server_default="{}"),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── extraction_schedules ──
    op.create_table(
        "extraction_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("interval_minutes", sa.Integer()),
        sa.Column("cron_hour", sa.Integer()),
        sa.Column("cron_minute", sa.Integer()),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── pipeline_requests ──
    op.create_table(
        "pipeline_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sei_url", sa.String(500), nullable=False),
        sa.Column("institution_name", sa.String(255)),
        sa.Column("detected_version", sa.String(50)),
        sa.Column("detected_family", sa.String(20)),
        sa.Column("scraper_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(30), nullable=False, server_default="analyzing"),
        sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id", ondelete="SET NULL")),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── system_configuration ──
    op.create_table(
        "system_configuration",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("updated_by", sa.String(255), server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── ParadeDB BM25 Indexes ──
    op.execute("""
        CREATE INDEX IF NOT EXISTS processes_search_idx ON processes
        USING bm25 (
            id,
            process_number,
            authority,
            category,
            category_status,
            access_type,
            unit,
            nickname,
            documents_data,
            extra_metadata,
            created_at,
            updated_at
        )
        WITH (key_field='id');
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS processes_search_idx;")
    op.drop_table("system_configuration")
    op.drop_table("pipeline_requests")
    op.drop_table("extraction_schedules")
    op.drop_table("extraction_tasks")
    op.drop_table("document_history")
    op.drop_table("receipts")
    op.drop_table("documents")
    op.drop_table("processes")
    op.drop_table("institution_scrapers")
    op.drop_table("institution_credentials")
    op.drop_table("institutions")
    op.drop_table("users")
