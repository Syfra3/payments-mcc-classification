"""External merchant and failed creation repositories."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.external_merchant import ExternalMerchant, FailedMerchantCreation
from app.core.context import get_session


class ExternalMerchantRepository:
    """Repository for ExternalMerchant entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, external_merchant: ExternalMerchant) -> ExternalMerchant:
        """Create and persist an external merchant."""
        session = self._get_session()
        session.add(external_merchant)
        await session.flush()
        return external_merchant

    async def get_by_provider_id(
        self, provider: str, provider_id: str
    ) -> Optional[ExternalMerchant]:
        """Get external merchant by provider and provider_id."""
        session = self._get_session()
        stmt = select(ExternalMerchant).where(
            and_(
                ExternalMerchant.provider == provider,
                ExternalMerchant.provider_id == provider_id,
                ExternalMerchant.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_merchant_id(self, merchant_id: UUID) -> List[ExternalMerchant]:
        """Get all external merchants for a given merchant."""
        session = self._get_session()
        stmt = select(ExternalMerchant).where(
            and_(
                ExternalMerchant.merchant_id == merchant_id,
                ExternalMerchant.deleted_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[ExternalMerchant]:
        """List all external merchants with pagination."""
        session = self._get_session()
        stmt = (
            select(ExternalMerchant)
            .where(ExternalMerchant.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def update(
        self, provider: str, provider_id: str, **kwargs
    ) -> Optional[ExternalMerchant]:
        """Update an external merchant."""
        session = self._get_session()
        external_merchant = await self.get_by_provider_id(provider, provider_id)
        if not external_merchant:
            return None

        for key, value in kwargs.items():
            setattr(external_merchant, key, value)

        await session.flush()
        return external_merchant

    async def delete(self, provider: str, provider_id: str) -> bool:
        """Soft-delete an external merchant."""
        session = self._get_session()
        external_merchant = await self.get_by_provider_id(provider, provider_id)
        if not external_merchant:
            return False

        external_merchant.deleted_at = func.now()
        await session.flush()
        return True

    async def associate_merchant(
        self, provider: str, provider_id: str, merchant_id: UUID
    ) -> Optional[ExternalMerchant]:
        """Associate an external merchant with an internal merchant."""
        session = self._get_session()
        external_merchant = await self.get_by_provider_id(provider, provider_id)
        if not external_merchant:
            return None

        external_merchant.merchant_id = merchant_id
        await session.flush()
        return external_merchant


class FailedMerchantCreationRepository:
    """Repository for FailedMerchantCreation entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, failed: FailedMerchantCreation) -> FailedMerchantCreation:
        """Create and persist a failed creation record."""
        session = self._get_session()
        session.add(failed)
        await session.flush()
        return failed

    async def get_by_id(self, failed_id: UUID) -> Optional[FailedMerchantCreation]:
        """Get failed creation record by ID."""
        session = self._get_session()
        stmt = select(FailedMerchantCreation).where(FailedMerchantCreation.id == failed_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_retryable(self, limit: int = 100) -> List[FailedMerchantCreation]:
        """List failed creations that are eligible for retry."""
        session = self._get_session()
        stmt = (
            select(FailedMerchantCreation)
            .where(
                and_(
                    FailedMerchantCreation.dead_lettered == False,
                    FailedMerchantCreation.next_retry_at <= func.now(),
                )
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def update_retry(
        self,
        failed_id: UUID,
        retry_count: int,
        last_retry_at: datetime,
        next_retry_at: datetime,
    ) -> Optional[FailedMerchantCreation]:
        """Update retry information for a failed creation."""
        session = self._get_session()
        failed = await self.get_by_id(failed_id)
        if not failed:
            return None

        failed.retry_count = retry_count
        failed.last_retry_at = last_retry_at
        failed.next_retry_at = next_retry_at
        await session.flush()
        return failed

    async def mark_dead_lettered(self, failed_id: UUID) -> Optional[FailedMerchantCreation]:
        """Mark a failed creation as dead-lettered (give up)."""
        session = self._get_session()
        failed = await self.get_by_id(failed_id)
        if not failed:
            return None

        failed.dead_lettered = True
        await session.flush()
        return failed
