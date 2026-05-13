"""MerchantMetadata repository for database operations."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.merchant_metadata import MerchantMetadata
from app.core.context import get_session


class MerchantMetadataRepository:
    """Repository for MerchantMetadata CRUD operations."""

    async def create(self, merchant_id: uuid.UUID, **kwargs) -> MerchantMetadata:
        """Create a new MerchantMetadata record.

        Args:
            merchant_id: UUID of the associated merchant
            **kwargs: Additional fields (human_created, human_modified, etc.)

        Returns:
            The created MerchantMetadata instance
        """
        session = get_session()
        metadata = MerchantMetadata(merchant_id=merchant_id, **kwargs)
        session.add(metadata)
        await session.flush()
        return metadata

    async def get_by_merchant_id(self, merchant_id: uuid.UUID) -> MerchantMetadata | None:
        """Retrieve metadata for a given merchant.

        Args:
            merchant_id: UUID of the merchant

        Returns:
            MerchantMetadata if found, None otherwise
        """
        session = get_session()
        result = await session.execute(
            select(MerchantMetadata).where(MerchantMetadata.merchant_id == merchant_id)
        )
        return result.scalar_one_or_none()

    async def update(self, merchant_id: uuid.UUID, **kwargs) -> MerchantMetadata | None:
        """Update metadata for a given merchant.

        Args:
            merchant_id: UUID of the merchant
            **kwargs: Fields to update

        Returns:
            Updated MerchantMetadata if found, None otherwise
        """
        session = get_session()
        metadata = await self.get_by_merchant_id(merchant_id)
        if metadata:
            for k, v in kwargs.items():
                setattr(metadata, k, v)
            await session.flush()
        return metadata

    async def get_or_create(
        self, merchant_id: uuid.UUID, **defaults
    ) -> MerchantMetadata:
        """Get or create metadata for a merchant with default values.

        Args:
            merchant_id: UUID of the merchant
            **defaults: Default values if creating new record

        Returns:
            Existing or newly created MerchantMetadata instance
        """
        existing = await self.get_by_merchant_id(merchant_id)
        return existing or await self.create(merchant_id=merchant_id, **defaults)
