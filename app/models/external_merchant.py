"""External merchant and failed creation ORM models."""

import uuid
from typing import Optional
from sqlalchemy import Column, String, UUID, JSON, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from app.models import Base, TimestampMixin, SoftDeleteMixin


class ExternalMerchant(Base, TimestampMixin, SoftDeleteMixin):
    """External merchant from a provider (e.g., Pomelo)."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, index=True)
    provider_id = Column(String(255), nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchant.id"), nullable=True)
    raw_data = Column(JSON, nullable=True)
    normalized_data = Column(JSON, nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="external_merchants", foreign_keys=[merchant_id])

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_external_merchant"),
    )


class FailedMerchantCreation(Base, TimestampMixin):
    """Track failed merchant creation attempts for retry logic."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_merchant_id = Column(UUID(as_uuid=True), ForeignKey("externalmerchant.id"), nullable=False)
    external_merchant_provider = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_retry_at = Column(DateTime(timezone=False), nullable=True)
    next_retry_at = Column(DateTime(timezone=False), nullable=True)
    dead_lettered = Column(Boolean, default=False, nullable=False)

    # Note: Composite foreign key not fully implemented here
    # In production, would use ForeignKeyConstraint for provider+id
