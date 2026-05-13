"""Merchant ORM model."""

import uuid
from typing import List, Optional
from sqlalchemy import Column, String, Float, UUID, event
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pgvector.sqlalchemy import Vector
from app.models import Base, TimestampMixin, SoftDeleteMixin


class Merchant(Base, TimestampMixin, SoftDeleteMixin):
    """Merchant entity representing a business."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    embedding = Column(Vector(1536), nullable=True)
    logo_url = Column(String(500), nullable=True)
    weight = Column(Float, default=1.0, nullable=False)

    # Relationships
    external_merchants = relationship(
        "ExternalMerchant",
        back_populates="merchant",
        foreign_keys="ExternalMerchant.merchant_id",
    )
    mccs = relationship(
        "Mcc",
        secondary="merchant_mcc",
        back_populates="merchants",
    )
    outbox_events = relationship(
        "OutboxEvent",
        back_populates="merchant",
        foreign_keys="OutboxEvent.merchant_id",
    )
    metadata_record = relationship(
        "MerchantMetadata",
        back_populates="merchant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        """Initialize merchant with uppercased name."""
        if "name" in kwargs:
            kwargs["name"] = kwargs["name"].upper()
        super().__init__(**kwargs)


@event.listens_for(Merchant, "before_insert")
def receive_before_insert(mapper, connection, target):
    """Ensure merchant name is uppercased before insert."""
    if target.name:
        target.name = target.name.upper()


@event.listens_for(Merchant, "before_update")
def receive_before_update(mapper, connection, target):
    """Ensure merchant name is uppercased before update."""
    if target.name:
        target.name = target.name.upper()
