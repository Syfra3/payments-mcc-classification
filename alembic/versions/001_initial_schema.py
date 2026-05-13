"""Initial schema creation

Revision ID: 001
Revises:
Create Date: 2026-05-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial tables."""
    # Install pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Category table
    op.create_table(
        "category",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_category_name"),
    )
    op.create_index("ix_category_name", "category", ["name"])

    # Merchant table
    op.create_table(
        "merchant",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_name", "merchant", ["name"])
    op.create_index("ix_merchant_provider", "merchant", ["provider"])

    # MCC table
    op.create_table(
        "mcc",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_mcc_code"),
    )
    op.create_index("ix_mcc_code", "mcc", ["code"])
    op.create_index("ix_mcc_code_category", "mcc", ["code", "category_id"])

    # MerchantMcc join table
    op.create_table(
        "merchant_mcc",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("mcc_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant.id"]),
        sa.ForeignKeyConstraint(["mcc_id"], ["mcc.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "mcc_id", name="uq_merchant_mcc"),
    )

    # ExternalMerchant table
    op.create_table(
        "externalmerchant",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("normalized_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_id", name="uq_external_merchant"),
    )
    op.create_index("ix_externalmerchant_provider", "externalmerchant", ["provider"])
    op.create_index("ix_externalmerchant_provider_id", "externalmerchant", ["provider_id"])

    # FailedMerchantCreation table
    op.create_table(
        "failedmerchantcreation",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("external_merchant_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("external_merchant_provider", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_retry_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("dead_lettered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["external_merchant_id"], ["externalmerchant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Embedding table
    op.create_table(
        "embedding",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embedding_resource_type", "embedding", ["resource_type"])
    op.create_index("ix_embedding_resource_id", "embedding", ["resource_id"])

    # OutboxEvent table
    op.create_table(
        "outboxevent",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("retry_count", sa.String(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("merchant_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outboxevent_aggregate_type", "outboxevent", ["aggregate_type"])
    op.create_index("ix_outboxevent_aggregate_id", "outboxevent", ["aggregate_id"])
    op.create_index("ix_outboxevent_status", "outboxevent", ["status"])
    op.create_index("ix_outboxevent_next_retry_at", "outboxevent", ["next_retry_at"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("outboxevent")
    op.drop_table("embedding")
    op.drop_table("failedmerchantcreation")
    op.drop_table("externalmerchant")
    op.drop_table("merchant_mcc")
    op.drop_table("mcc")
    op.drop_table("merchant")
    op.drop_table("category")
