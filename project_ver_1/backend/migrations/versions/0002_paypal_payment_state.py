"""Align PayPal payment models and persist checkout, payout, and webhook state.

Revision ID: 0002_paypal_payment_state
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_paypal_payment_state"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True, server_default=""))
    op.add_column("users", sa.Column("age", sa.Integer()))
    op.add_column(
        "users",
        sa.Column("coppa_consent_status", sa.String(length=50), nullable=True, server_default="NOT_REQUIRED"),
    )
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("families", sa.Column("created_by_user_id", sa.Integer()))
    op.add_column("families", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("accounts", sa.Column("family_id", sa.Integer()))
    op.add_column(
        "accounts",
        sa.Column("account_type", sa.String(length=50), nullable=False, server_default="PARENT_WALLET"),
    )
    op.add_column("accounts", sa.Column("balance", sa.Float(), nullable=False, server_default="0"))
    op.add_column("accounts", sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"))
    op.add_column("accounts", sa.Column("paypal_account_id", sa.String(length=255)))
    op.add_column("accounts", sa.Column("paypal_encrypted_token", sa.Text()))
    op.add_column("accounts", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("accounts", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("transactions", sa.Column("account_id", sa.Integer()))
    op.add_column("transactions", sa.Column("description", sa.Text()))
    op.add_column("transactions", sa.Column("flagged_reason", sa.Text()))
    op.add_column("transactions", sa.Column("parent_payment_id", sa.String(length=255)))
    op.add_column("transactions", sa.Column("refund_id", sa.String(length=255)))
    op.add_column("transactions", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("budget_envelopes", sa.Column("name", sa.String(length=80)))
    op.add_column("budget_envelopes", sa.Column("current_spent", sa.Float(), nullable=False, server_default="0"))
    op.add_column("budget_envelopes", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("budget_envelopes", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("purchase_requests", sa.Column("child_id", sa.Integer()))
    op.add_column("purchase_requests", sa.Column("item_name", sa.String(length=255)))
    op.add_column("purchase_requests", sa.Column("store_url", sa.Text()))
    op.add_column("purchase_requests", sa.Column("ai_risk_assessment", sa.Text()))
    op.add_column("purchase_requests", sa.Column("rejection_reason", sa.Text()))
    op.add_column("purchase_requests", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100)),
        sa.Column("resource_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PROCESSING"),
        sa.Column("summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_processed_webhook_events_resource_id",
        "processed_webhook_events",
        ["resource_id"],
    )
    op.add_column("purchase_requests", sa.Column("paypal_order_id", sa.String(length=255)))
    op.add_column("purchase_requests", sa.Column("paypal_approval_url", sa.Text()))
    op.add_column("purchase_requests", sa.Column("paypal_capture_id", sa.String(length=255)))
    op.add_column("purchase_requests", sa.Column("paypal_payment_status", sa.String(length=50)))
    op.add_column("allowance_schedules", sa.Column("child_id", sa.Integer()))
    op.add_column("allowance_schedules", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("allowance_schedules", sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("allowance_schedules", sa.Column("freeze_reason", sa.Text()))
    op.add_column("allowance_schedules", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column("allowance_schedules", sa.Column("last_payout_date", sa.DateTime(timezone=True)))
    op.add_column("allowance_schedules", sa.Column("last_payout_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("allowance_schedules", sa.Column("last_payout_status", sa.String(length=50)))
    op.add_column("allowance_schedules", sa.Column("last_payout_batch_id", sa.String(length=255)))
    op.add_column("allowance_schedules", sa.Column("last_payout_error", sa.Text()))

    op.execute(
        "UPDATE purchase_requests SET child_id = child_user_id, item_name = merchant, "
        "store_url = item_url, ai_risk_assessment = note"
    )
    op.execute(
        "UPDATE allowance_schedules SET child_id = child_user_id, is_active = active"
    )
    op.execute(
        "UPDATE budget_envelopes SET name = category_name, current_spent = spent_amount"
    )


def downgrade() -> None:
    op.drop_column("allowance_schedules", "last_payout_error")
    op.drop_column("allowance_schedules", "last_payout_batch_id")
    op.drop_column("allowance_schedules", "last_payout_status")
    op.drop_column("allowance_schedules", "last_payout_attempt_at")
    op.drop_column("allowance_schedules", "last_payout_date")
    op.drop_column("purchase_requests", "paypal_payment_status")
    op.drop_column("purchase_requests", "paypal_capture_id")
    op.drop_column("purchase_requests", "paypal_approval_url")
    op.drop_column("purchase_requests", "paypal_order_id")
    op.drop_column("allowance_schedules", "updated_at")
    op.drop_column("allowance_schedules", "freeze_reason")
    op.drop_column("allowance_schedules", "is_frozen")
    op.drop_column("allowance_schedules", "is_active")
    op.drop_column("allowance_schedules", "child_id")
    op.drop_index(
        "ix_processed_webhook_events_resource_id",
        table_name="processed_webhook_events",
    )
    op.drop_table("processed_webhook_events")
    op.drop_column("purchase_requests", "updated_at")
    op.drop_column("purchase_requests", "rejection_reason")
    op.drop_column("purchase_requests", "ai_risk_assessment")
    op.drop_column("purchase_requests", "store_url")
    op.drop_column("purchase_requests", "item_name")
    op.drop_column("purchase_requests", "child_id")
    op.drop_column("budget_envelopes", "updated_at")
    op.drop_column("budget_envelopes", "created_at")
    op.drop_column("budget_envelopes", "current_spent")
    op.drop_column("budget_envelopes", "name")
    op.drop_column("transactions", "updated_at")
    op.drop_column("transactions", "refund_id")
    op.drop_column("transactions", "parent_payment_id")
    op.drop_column("transactions", "flagged_reason")
    op.drop_column("transactions", "description")
    op.drop_column("transactions", "account_id")
    op.drop_column("accounts", "updated_at")
    op.drop_column("accounts", "is_active")
    op.drop_column("accounts", "paypal_encrypted_token")
    op.drop_column("accounts", "paypal_account_id")
    op.drop_column("accounts", "currency")
    op.drop_column("accounts", "balance")
    op.drop_column("accounts", "account_type")
    op.drop_column("accounts", "family_id")
    op.drop_column("families", "updated_at")
    op.drop_column("families", "created_by_user_id")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "coppa_consent_status")
    op.drop_column("users", "age")
    op.drop_column("users", "name")
