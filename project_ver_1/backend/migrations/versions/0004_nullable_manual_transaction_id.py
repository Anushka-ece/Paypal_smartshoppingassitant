"""Allow family-entered expenses without a PayPal capture ID.

Revision ID: 0004_nullable_manual_transaction_id
Revises: 0003_auth_and_paypal_oauth
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_nullable_manual_transaction_id"
down_revision = "0003_auth_and_paypal_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column(
            "paypal_transaction_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE transactions "
        "SET paypal_transaction_id = 'manual-' || id "
        "WHERE paypal_transaction_id IS NULL"
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column(
            "paypal_transaction_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
