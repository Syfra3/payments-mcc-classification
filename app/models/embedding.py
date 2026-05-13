"""Embedding and Outbox ORM models."""

import uuid
from typing import Optional
from sqlalchemy import Column, String, UUID, JSON, Text, DateTime
from pgvector.sqlalchemy import Vector
from app.models import Base, TimestampMixin


class Embedding(Base, TimestampMixin):
    """Vector embedding storage for similarity search."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_type = Column(String(50), nullable=False, index=True)  # e.g., "merchant", "mcc"
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    embedding = Column(Vector(1536), nullable=False)
    metadata = Column(JSON, nullable=True)


class OutboxEvent(Base, TimestampMixin):
    """Outbox event for reliable event delivery."""

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_type = Column(String(50), nullable=False, index=True)  # e.g., "Merchant"
    aggregate_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)  # e.g., "MerchantCreated"
    payload = Column(JSON, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, DELIVERED, FAILED, DEAD_LETTERED
    retry_count = Column(String, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    delivered_at = Column(DateTime(timezone=False), nullable=True)
    next_retry_at = Column(DateTime(timezone=False), nullable=True, index=True)
    merchant_id = Column(UUID(as_uuid=True), nullable=True)

    # Relationships defined in merchant.py due to import order
