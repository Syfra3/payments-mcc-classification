"""Add tenant isolation columns to core tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id columns and establish tenant isolation."""
    # Step 1: Add tenant_id columns (nullable initially)
    op.add_column(
        "merchant",
        sa.Column("tenant_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "category",
        sa.Column("tenant_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "mcc",
        sa.Column("tenant_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "validation_rules",
        sa.Column("tenant_id", sa.String(100), nullable=True),
    ) if op.get_context().dialect.name == "postgresql" else None

    # Step 2: Backfill existing rows with default tenant
    op.execute("UPDATE merchant SET tenant_id = 'default' WHERE tenant_id IS NULL")
    op.execute("UPDATE category SET tenant_id = 'default' WHERE tenant_id IS NULL")
    op.execute("UPDATE mcc SET tenant_id = 'default' WHERE tenant_id IS NULL")
    # Only update if validation_rules table exists (may be from a later version)
    try:
        op.execute("UPDATE validation_rules SET tenant_id = 'default' WHERE tenant_id IS NULL")
    except Exception:
        pass

    # Step 3: Set NOT NULL constraint
    op.alter_column(
        "merchant",
        "tenant_id",
        nullable=False,
        server_default="default",
    )
    op.alter_column(
        "category",
        "tenant_id",
        nullable=False,
        server_default="default",
    )
    op.alter_column(
        "mcc",
        "tenant_id",
        nullable=False,
        server_default="default",
    )

    # Step 4: Create indexes for efficient tenant-scoped queries
    op.create_index("ix_merchant_tenant_id", "merchant", ["tenant_id"])
    op.create_index("ix_category_tenant_id", "category", ["tenant_id"])
    op.create_index("ix_mcc_tenant_id", "mcc", ["tenant_id"])

    # Step 5: Update unique constraints to include tenant_id
    # Drop old unique constraints
    op.drop_constraint("uq_category_name", "category", type_="unique")
    op.drop_constraint("uq_mcc_code", "mcc", type_="unique")

    # Create new composite unique constraints
    op.create_unique_constraint(
        "uq_category_name_tenant_id",
        "category",
        ["name", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_mcc_code_tenant_id",
        "mcc",
        ["code", "tenant_id"],
    )


def downgrade() -> None:
    """Remove tenant isolation changes."""
    # Drop composite unique constraints
    op.drop_constraint(
        "uq_category_name_tenant_id",
        "category",
        type_="unique",
    )
    op.drop_constraint(
        "uq_mcc_code_tenant_id",
        "mcc",
        type_="unique",
    )

    # Recreate original unique constraints
    op.create_unique_constraint(
        "uq_category_name",
        "category",
        ["name"],
    )
    op.create_unique_constraint(
        "uq_mcc_code",
        "mcc",
        ["code"],
    )

    # Drop indexes
    op.drop_index("ix_merchant_tenant_id", table_name="merchant")
    op.drop_index("ix_category_tenant_id", table_name="category")
    op.drop_index("ix_mcc_tenant_id", table_name="mcc")

    # Drop tenant_id columns
    op.drop_column("merchant", "tenant_id")
    op.drop_column("category", "tenant_id")
    op.drop_column("mcc", "tenant_id")
    # Only drop if it exists
    try:
        op.drop_column("validation_rules", "tenant_id")
    except Exception:
        pass
