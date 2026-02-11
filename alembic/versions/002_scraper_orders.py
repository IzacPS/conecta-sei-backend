"""Scraper orders, payments, subscriptions

Revision ID: 002_scraper_orders
Revises: 001_v2_web
Create Date: 2026-02-09

Tables:
- scraper_orders (commercial order linked to pipeline_request)
- payments (individual payment records)
- subscriptions (recurring billing)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002_scraper_orders"
down_revision = "001_v2_web"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── scraper_orders ──
    op.create_table(
        "scraper_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_request_id", sa.Integer(), sa.ForeignKey("pipeline_requests.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("setup_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(30), nullable=False, server_default="quote_sent"),
        sa.Column("admin_notes", sa.Text()),
        sa.Column("client_notes", sa.Text()),
        sa.Column("estimated_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("quoted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── payments ──
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("scraper_orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("payment_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("external_provider", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("external_id", sa.String(255), index=True),
        sa.Column("external_checkout_url", sa.Text()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── subscriptions ──
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("scraper_orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("interval", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("external_subscription_id", sa.String(255), index=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("payments")
    op.drop_table("scraper_orders")
