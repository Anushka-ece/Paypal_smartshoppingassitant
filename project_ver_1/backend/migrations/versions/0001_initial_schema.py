"""Initial family budgeting schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("paypal_payer_id", sa.String(length=128)),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("paypal_payer_id", sa.String(length=128)),
        sa.Column("encrypted_access_token", sa.Text()),
        sa.Column("encrypted_refresh_token", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "paypal_payer_id", name="uq_user_paypal_account"),
    )
    op.create_table(
        "budget_envelopes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("category_name", sa.String(length=80), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("spent_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.UniqueConstraint("family_id", "user_id", "category_name", name="uq_family_user_envelope"),
    )
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("paypal_transaction_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("merchant_name", sa.String(length=255), nullable=False, server_default="Unknown merchant"),
        sa.Column("clean_merchant_name", sa.String(length=255)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("category", sa.String(length=80)),
        sa.Column("subcategory", sa.String(length=100)),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("risk_level", sa.String(length=10), nullable=False, server_default="LOW"),
        sa.Column("matched_rules", sa.JSON()),
        sa.Column("refunded_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("dispute_id", sa.String(length=128)),
        sa.Column("dispute_status", sa.String(length=40)),
        sa.Column("review_decision", sa.String(length=30)),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("account_code", sa.String(length=80), nullable=False),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paypal_event_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("processing_status", sa.String(length=20), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "allowance_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("child_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_payout_request_id", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "allowance_payouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("allowance_schedules.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("paypal_batch_id", sa.String(length=128)),
        sa.Column("response_json", sa.JSON()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("child_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("item_url", sa.Text()),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("note", sa.Text()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    index_columns = {
        "users": ["family_id", "email"],
        "accounts": ["user_id", "paypal_payer_id"],
        "budget_envelopes": ["family_id", "user_id"],
        "transactions": ["family_id", "user_id", "paypal_transaction_id", "dispute_id"],
        "ledger_entries": ["transaction_id"],
        "policy_rules": ["family_id"],
        "webhook_events": ["paypal_event_id"],
        "allowance_schedules": ["family_id", "child_user_id", "next_run_at"],
        "allowance_payouts": ["schedule_id"],
        "purchase_requests": ["family_id", "child_user_id"],
    }
    for table, columns in index_columns.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column], unique=False)


def downgrade() -> None:
    for table in (
        "purchase_requests", "allowance_payouts", "allowance_schedules", "webhook_events",
        "ledger_entries", "transactions", "policy_rules", "budget_envelopes", "accounts", "users", "families",
    ):
        op.drop_table(table)
