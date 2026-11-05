"""Make the legacy budget category field optional.

Revision ID: 0005_nullable_legacy_budget_category
Revises: 0004_nullable_manual_transaction_id
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_nullable_legacy_budget_category"
down_revision = "0004_nullable_manual_transaction_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE budget_envelopes "
        "SET name = COALESCE(name, category_name), "
        "category_name = COALESCE(category_name, name)"
    )
    with op.batch_alter_table("budget_envelopes") as batch_op:
        batch_op.alter_column(
            "category_name",
            existing_type=sa.String(length=80),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE budget_envelopes "
        "SET category_name = COALESCE(category_name, name)"
    )
    with op.batch_alter_table("budget_envelopes") as batch_op:
        batch_op.alter_column(
            "category_name",
            existing_type=sa.String(length=80),
            nullable=False,
        )
