"""Merchant repository for data access."""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.merchant import Merchant
from app.core.context import get_session


class MerchantRepository:
    """Repository for Merchant entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, merchant: Merchant) -> Merchant:
        """Create and persist a merchant."""
        session = self._get_session()
        session.add(merchant)
        await session.flush()
        return merchant

    async def get_by_id(self, merchant_id: UUID) -> Optional[Merchant]:
        """Get merchant by ID."""
        session = self._get_session()
        stmt = select(Merchant).where(
            and_(Merchant.id == merchant_id, Merchant.deleted_at.is_(None))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Merchant]:
        """Get merchant by name (case-insensitive)."""
        session = self._get_session()
        upper_name = name.upper()
        stmt = select(Merchant).where(
            and_(Merchant.name == upper_name, Merchant.deleted_at.is_(None))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[Merchant]:
        """List all merchants with pagination."""
        session = self._get_session()
        stmt = (
            select(Merchant)
            .where(Merchant.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def search_by_similarity(
        self,
        embedding: List[float],
        threshold: float = 0.0,
        limit: int = 10,
    ) -> List[Tuple[Merchant, float]]:
        """Search merchants by embedding similarity."""
        session = self._get_session()

        # PostgreSQL pgvector similarity using <=> operator (cosine distance)
        # Note: <=> returns distance, not similarity, so we compute similarity = 1 - distance
        stmt = (
            select(
                Merchant,
                (1 - (Merchant.embedding.op("<->")(embedding))).label("similarity"),
            )
            .where(
                and_(
                    Merchant.embedding.isnot(None),
                    Merchant.deleted_at.is_(None),
                    (1 - (Merchant.embedding.op("<->")(embedding))) >= threshold,
                )
            )
            .order_by((1 - (Merchant.embedding.op("<->")(embedding))).desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def update(self, merchant_id: UUID, **kwargs) -> Optional[Merchant]:
        """Update a merchant."""
        session = self._get_session()
        merchant = await self.get_by_id(merchant_id)
        if not merchant:
            return None

        for key, value in kwargs.items():
            if key == "name" and value:
                value = value.upper()
            setattr(merchant, key, value)

        await session.flush()
        return merchant

    async def delete(self, merchant_id: UUID) -> bool:
        """Soft-delete a merchant."""
        session = self._get_session()
        merchant = await self.get_by_id(merchant_id)
        if not merchant:
            return False

        merchant.deleted_at = func.now()
        await session.flush()
        return True

    async def bulk_create(self, merchants: List[Merchant]) -> List[Merchant]:
        """Create multiple merchants in a single operation."""
        session = self._get_session()
        session.add_all(merchants)
        await session.flush()
        return merchants

    async def count(self) -> int:
        """Count total merchants."""
        session = self._get_session()
        stmt = select(func.count()).select_from(Merchant).where(Merchant.deleted_at.is_(None))
        result = await session.execute(stmt)
        return result.scalar() or 0
