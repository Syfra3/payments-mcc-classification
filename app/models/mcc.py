"""MCC (Merchant Category Code) ORM models."""

import uuid
from typing import List, Optional
from sqlalchemy import Column, String, UUID, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.models import Base, TimestampMixin, SoftDeleteMixin


class Category(Base, TimestampMixin):
    """Category for grouping MCCs."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Relationships
    mccs = relationship("Mcc", back_populates="category")


class Mcc(Base, TimestampMixin, SoftDeleteMixin):
    """Merchant Category Code (MCC) entity."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(10), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id"), nullable=True)
    embedding = Column(Vector(768), nullable=True)

    # Relationships
    category = relationship("Category", back_populates="mccs")
    merchants = relationship(
        "Merchant",
        secondary="merchant_mcc",
        back_populates="mccs",
    )

    __table_args__ = (Index("ix_mcc_code_category", "code", "category_id"),)


class MerchantMcc(Base, TimestampMixin):
    """Join table for merchant-MCC many-to-many relationship."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchant.id"), nullable=False)
    mcc_id = Column(UUID(as_uuid=True), ForeignKey("mcc.id"), nullable=False)

    # Relationships
    merchant = relationship("Merchant")
    mcc = relationship("Mcc")

    __table_args__ = (UniqueConstraint("merchant_id", "mcc_id", name="uq_merchant_mcc"),)
