"""Add merchant_metadata table

Revision ID: 002
Revises: 001
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create merchant_metadata table."""
    op.create_table(
        "merchant_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("human_created", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("human_modified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mcc_association_type", sa.String(50), nullable=True),
        sa.Column("voucher_association_type", sa.String(50), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", name="uq_merchant_metadata_merchant_id"),
    )
    op.create_index(
        "ix_merchant_metadata_merchant_id", "merchant_metadata", ["merchant_id"]
    )


def downgrade() -> None:
    """Drop merchant_metadata table."""
    op.drop_index("ix_merchant_metadata_merchant_id", table_name="merchant_metadata")
    op.drop_table("merchant_metadata")
