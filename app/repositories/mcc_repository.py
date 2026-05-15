"""MCC and Category repositories for data access."""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mcc import Mcc, Category, MerchantMcc
from app.core.context import get_session


class MccRepository:
    """Repository for MCC entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, mcc: Mcc) -> Mcc:
        """Create and persist an MCC."""
        session = self._get_session()
        session.add(mcc)
        await session.flush()
        return mcc

    async def get_by_id(self, mcc_id: UUID, tenant_id: str = "default") -> Optional[Mcc]:
        """Get MCC by ID, scoped to tenant."""
        session = self._get_session()
        stmt = select(Mcc).where(
            and_(
                Mcc.id == mcc_id,
                Mcc.tenant_id == tenant_id,
                Mcc.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, tenant_id: str = "default") -> Optional[Mcc]:
        """Get MCC by code, scoped to tenant."""
        session = self._get_session()
        stmt = select(Mcc).where(
            and_(
                Mcc.code == code,
                Mcc.tenant_id == tenant_id,
                Mcc.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, tenant_id: str = "default", skip: int = 0, limit: int = 100) -> List[Mcc]:
        """List all MCCs for a tenant with pagination."""
        session = self._get_session()
        stmt = (
            select(Mcc)
            .where(
                and_(
                    Mcc.tenant_id == tenant_id,
                    Mcc.deleted_at.is_(None),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def search_by_similarity(
        self,
        embedding: List[float],
        tenant_id: str = "default",
        threshold: float = 0.0,
        limit: int = 10,
    ) -> List[Tuple[Mcc, float]]:
        """Search MCCs by embedding similarity, scoped to tenant."""
        session = self._get_session()

        stmt = (
            select(
                Mcc,
                (1 - (Mcc.embedding.op("<->")(embedding))).label("similarity"),
            )
            .where(
                and_(
                    Mcc.tenant_id == tenant_id,
                    Mcc.embedding.isnot(None),
                    Mcc.deleted_at.is_(None),
                    (1 - (Mcc.embedding.op("<->")(embedding))) >= threshold,
                )
            )
            .order_by((1 - (Mcc.embedding.op("<->")(embedding))).desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def update(self, mcc_id: UUID, tenant_id: str = "default", **kwargs) -> Optional[Mcc]:
        """Update an MCC, scoped to tenant."""
        session = self._get_session()
        mcc = await self.get_by_id(mcc_id, tenant_id)
        if not mcc:
            return None

        for key, value in kwargs.items():
            setattr(mcc, key, value)

        await session.flush()
        return mcc

    async def delete(self, mcc_id: UUID, tenant_id: str = "default") -> bool:
        """Soft-delete an MCC, scoped to tenant."""
        session = self._get_session()
        mcc = await self.get_by_id(mcc_id, tenant_id)
        if not mcc:
            return False

        mcc.deleted_at = func.now()
        await session.flush()
        return True

    async def add_merchant_to_mcc(
        self, mcc_id: UUID, merchant_id: UUID
    ) -> MerchantMcc:
        """Associate a merchant with an MCC."""
        session = self._get_session()
        merchant_mcc = MerchantMcc(merchant_id=merchant_id, mcc_id=mcc_id)
        session.add(merchant_mcc)
        await session.flush()
        return merchant_mcc

    async def remove_merchant_from_mcc(self, mcc_id: UUID, merchant_id: UUID) -> bool:
        """Remove association between merchant and MCC."""
        session = self._get_session()
        stmt = select(MerchantMcc).where(
            and_(MerchantMcc.mcc_id == mcc_id, MerchantMcc.merchant_id == merchant_id)
        )
        result = await session.execute(stmt)
        merchant_mcc = result.scalar_one_or_none()
        if not merchant_mcc:
            return False

        await session.delete(merchant_mcc)
        await session.flush()
        return True


class CategoryRepository:
    """Repository for Category entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, category: Category) -> Category:
        """Create and persist a category."""
        session = self._get_session()
        session.add(category)
        await session.flush()
        return category

    async def get_by_id(self, category_id: UUID, tenant_id: str = "default") -> Optional[Category]:
        """Get category by ID, scoped to tenant."""
        session = self._get_session()
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.tenant_id == tenant_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, tenant_id: str = "default") -> Optional[Category]:
        """Get category by name, scoped to tenant."""
        session = self._get_session()
        stmt = select(Category).where(
            and_(Category.name == name, Category.tenant_id == tenant_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, tenant_id: str = "default") -> List[Category]:
        """List all categories for a tenant."""
        session = self._get_session()
        stmt = select(Category).where(Category.tenant_id == tenant_id)
        result = await session.execute(stmt)
        return result.scalars().all()
