"""MerchantMetadata ORM model."""

import uuid
from typing import Optional
from sqlalchemy import Column, String, Boolean, UUID, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models import Base, TimestampMixin


class MerchantMetadata(Base, TimestampMixin):
    """Metadata for a Merchant, tracking creation/modification state and associations."""

    __tablename__ = "merchant_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchant.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    human_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mcc_association_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    voucher_association_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationship back to Merchant
    merchant: Mapped["Merchant"] = relationship(
        back_populates="metadata_record",
        foreign_keys=[merchant_id],
    )
