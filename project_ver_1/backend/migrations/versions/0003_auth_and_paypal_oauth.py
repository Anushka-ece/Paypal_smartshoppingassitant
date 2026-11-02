"""Add revocable auth tokens, OAuth state, and separate PayPal tokens.

Revision ID: 0003_auth_and_paypal_oauth
Revises: 0002_paypal_payment_state
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_auth_and_paypal_oauth"
down_revision = "0002_paypal_payment_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("accounts", sa.Column("paypal_encrypted_refresh_token", sa.Text()))
    op.add_column("accounts", sa.Column("paypal_access_token_expires_at", sa.DateTime(timezone=True)))
    op.create_index(
        "uq_accounts_paypal_account_id",
        "accounts",
        ["paypal_account_id"],
        unique=True,
    )
    op.create_table(
        "paypal_oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("state_hash", name="uq_paypal_oauth_states_state_hash"),
    )
    op.create_index("ix_paypal_oauth_states_state_hash", "paypal_oauth_states", ["state_hash"])
    op.create_index("ix_paypal_oauth_states_user_id", "paypal_oauth_states", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_paypal_oauth_states_user_id", table_name="paypal_oauth_states")
    op.drop_index("ix_paypal_oauth_states_state_hash", table_name="paypal_oauth_states")
    op.drop_table("paypal_oauth_states")
    op.drop_index("uq_accounts_paypal_account_id", table_name="accounts")
    op.drop_column("accounts", "paypal_access_token_expires_at")
    op.drop_column("accounts", "paypal_encrypted_refresh_token")
    op.drop_column("users", "auth_token_version")
