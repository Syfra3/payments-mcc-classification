"""SQLAlchemy ORM models and base configuration."""

from datetime import datetime
from typing import Any, Dict
from sqlalchemy import DateTime, func, Column
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.ext.hybrid import hybrid_property


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        list: dict,
    }

    @declared_attr
    def __tablename__(cls) -> str:
        """Auto-generate table name from class name (lowercase)."""
        return cls.__name__.lower()


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps to models."""

    @declared_attr
    def created_at(cls):
        """Creation timestamp."""
        return Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    @declared_attr
    def updated_at(cls):
        """Last update timestamp."""
        return Column(
            DateTime(timezone=False),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


class SoftDeleteMixin:
    """Mixin that adds soft-delete functionality via deleted_at timestamp."""

    @declared_attr
    def deleted_at(cls):
        """Soft delete timestamp. NULL means not deleted."""
        return Column(DateTime(timezone=False), nullable=True, default=None)

    @hybrid_property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted."""
        return self.deleted_at is not None

    @hybrid_property
    def is_active(self) -> bool:
        """Check if the record is active (not deleted)."""
        return self.deleted_at is None


from app.models.merchant_metadata import MerchantMetadata  # noqa: F401

__all__ = ["Base", "TimestampMixin", "SoftDeleteMixin", "MerchantMetadata"]
