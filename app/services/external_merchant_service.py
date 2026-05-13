"""External merchant business logic service."""

from uuid import UUID
from typing import Optional
from app.core.context import transactional
from app.core.exceptions import AppException, ResourceNotFound
from app.models.external_merchant import ExternalMerchant
from app.repositories.external_merchant_repository import ExternalMerchantRepository
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.outbox_repository import OutboxRepository
from app.schemas import (
    ExternalMerchantCreateRequest,
    ExternalMerchantResponse,
    ExternalMerchantListResponse,
)
from app.providers.card.interface import ICardProvider


class ExternalMerchantService:
    """Service for external merchant registration and management."""

    def __init__(
        self,
        card_provider: ICardProvider,
        external_merchant_repo: Optional[ExternalMerchantRepository] = None,
        merchant_repo: Optional[MerchantRepository] = None,
        outbox_repo: Optional[OutboxRepository] = None,
    ):
        """
        Initialize service with dependencies.

        Args:
            card_provider: Card provider for normalization
            external_merchant_repo: External merchant repository
            merchant_repo: Merchant repository
            outbox_repo: Outbox repository for events
        """
        self._card = card_provider
        self._external_repo = external_merchant_repo or ExternalMerchantRepository()
        self._merchant_repo = merchant_repo or MerchantRepository()
        self._outbox_repo = outbox_repo or OutboxRepository()

    @transactional
    async def register(
        self, request: ExternalMerchantCreateRequest
    ) -> ExternalMerchantResponse:
        """
        Register a new external merchant.

        Args:
            request: Registration request with provider, provider_id, raw_data

        Returns:
            Created external merchant response

        Raises:
            AppException: If merchant already registered
        """
        # Check not already registered
        existing = await self._external_repo.get_by_provider_id(
            request.provider, request.provider_id
        )
        if existing:
            raise AppException(
                f"External merchant {request.provider}:{request.provider_id} already registered",
                status_code=409,
            )

        # Normalize data via card provider
        try:
            normalized_data = await self._card.normalize_merchant(request.raw_data)
        except Exception as e:
            raise AppException(
                f"Failed to normalize merchant data: {str(e)}",
                status_code=400,
            )

        # Create external merchant record
        ext_merchant = ExternalMerchant(
            provider=request.provider,
            provider_id=request.provider_id,
            raw_data=request.raw_data,
            normalized_data=normalized_data,
        )
        ext_merchant = await self._external_repo.create(ext_merchant)

        return ExternalMerchantResponse.model_validate(ext_merchant)

    @transactional
    async def get_by_provider_id(
        self, provider: str, provider_id: str
    ) -> ExternalMerchantResponse:
        """
        Get external merchant by provider and ID.

        Args:
            provider: Provider name (e.g., "pomelo")
            provider_id: Provider's merchant ID

        Returns:
            External merchant response

        Raises:
            ResourceNotFound: If merchant not found
        """
        ext_merchant = await self._external_repo.get_by_provider_id(provider, provider_id)
        if not ext_merchant:
            raise ResourceNotFound(
                f"External merchant {provider}:{provider_id} not found"
            )
        return ExternalMerchantResponse.model_validate(ext_merchant)

    @transactional
    async def list_all(
        self, skip: int = 0, limit: int = 100
    ) -> ExternalMerchantListResponse:
        """
        List all external merchants with pagination.

        Args:
            skip: Offset for pagination
            limit: Max results

        Returns:
            Paginated external merchant list
        """
        if skip < 0:
            skip = 0
        if limit < 1:
            limit = 1
        if limit > 500:
            limit = 500

        ext_merchants, total = await self._external_repo.list_all(skip, limit)
        return ExternalMerchantListResponse(
            items=[ExternalMerchantResponse.model_validate(em) for em in ext_merchants],
            total=total,
            skip=skip,
            limit=limit,
        )

    @transactional
    async def associate_merchant(
        self, provider: str, provider_id: str, merchant_id: UUID
    ) -> ExternalMerchantResponse:
        """
        Associate an external merchant with an internal merchant.

        Args:
            provider: Provider name
            provider_id: Provider's merchant ID
            merchant_id: Internal merchant UUID

        Returns:
            Updated external merchant response

        Raises:
            ResourceNotFound: If external merchant or merchant not found
        """
        # Fetch external merchant
        ext_merchant = await self._external_repo.get_by_provider_id(provider, provider_id)
        if not ext_merchant:
            raise ResourceNotFound(
                f"External merchant {provider}:{provider_id} not found"
            )

        # Check merchant exists
        merchant = await self._merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise ResourceNotFound(f"Merchant {merchant_id} not found")

        # Update association
        ext_merchant.merchant_id = merchant_id
        ext_merchant = await self._external_repo.update(
            ext_merchant.id, merchant_id=merchant_id
        )

        # Create outbox event for downstream notification
        await self._outbox_repo.create_event(
            event_type="external_merchant.associated",
            aggregate_id=ext_merchant.id,
            aggregate_type="ExternalMerchant",
            payload={
                "provider": provider,
                "provider_id": provider_id,
                "merchant_id": str(merchant_id),
            },
        )

        return ExternalMerchantResponse.model_validate(ext_merchant)

    @transactional
    async def delete(self, provider: str, provider_id: str) -> bool:
        """
        Soft delete an external merchant.

        Args:
            provider: Provider name
            provider_id: Provider's merchant ID

        Returns:
            True if deleted, False if not found
        """
        ext_merchant = await self._external_repo.get_by_provider_id(provider, provider_id)
        if not ext_merchant:
            return False

        await self._external_repo.delete(ext_merchant.id)
        return True
