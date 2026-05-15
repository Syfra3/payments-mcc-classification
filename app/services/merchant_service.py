"""Merchant business logic service."""

from uuid import UUID
from typing import Optional
import structlog
from app.core.context import transactional
from app.core.exceptions import AppException, ResourceNotFound
from app.models.merchant import Merchant
from app.models.embedding import Embedding
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.mcc_repository import MccRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.schemas import (
    MerchantCreateRequest,
    MerchantUpdateRequest,
    MerchantResponse,
    MerchantListResponse,
)
from app.providers.llm.interface import ILlmProvider
from app.providers.embedding import store_embedding, search_embeddings_by_similarity

logger = structlog.get_logger(__name__)


class MerchantService:
    """Service for merchant CRUD and business operations."""

    def __init__(
        self,
        llm_provider: ILlmProvider,
        merchant_repo: Optional[MerchantRepository] = None,
        mcc_repo: Optional[MccRepository] = None,
        embedding_repo: Optional[EmbeddingRepository] = None,
    ):
        """
        Initialize service with dependencies.

        Args:
            llm_provider: LLM provider for embeddings
            merchant_repo: Merchant repository (uses DI if None)
            mcc_repo: MCC repository (uses DI if None)
            embedding_repo: Embedding repository (uses DI if None)
        """
        self._llm = llm_provider
        self._merchant_repo = merchant_repo or MerchantRepository()
        self._mcc_repo = mcc_repo or MccRepository()
        self._embedding_repo = embedding_repo or EmbeddingRepository()

    @transactional
    async def create(self, request: MerchantCreateRequest) -> MerchantResponse:
        """
        Create a new merchant.

        Args:
            request: Merchant creation request with name, provider, optional mcc_codes

        Returns:
            Created merchant response

        Raises:
            AppException: If merchant with same name already exists
        """
        # Validate name is not empty
        if not request.name or not request.name.strip():
            raise AppException("Merchant name cannot be empty", status_code=400)

        # Check for duplicates by name
        existing = await self._merchant_repo.get_by_name(request.name)
        if existing:
            raise AppException(
                f"Merchant with name '{request.name}' already exists",
                status_code=409,
            )

        # Create merchant record
        merchant = Merchant(
            name=request.name,
            provider=request.provider,
            logo_url=request.logo_url,
            metadata=request.metadata or {},
        )
        merchant = await self._merchant_repo.create(merchant)

        # Assign MCCs if provided
        if request.mcc_codes:
            for mcc_code in request.mcc_codes:
                mcc = await self._mcc_repo.get_by_code(mcc_code)
                if mcc:
                    await self._mcc_repo.add_merchant_to_mcc(mcc.id, merchant.id)

        # Generate embedding for merchant name
        try:
            embedding_vec = await self._llm.embed(merchant.name)
            await store_embedding(
                "merchant",
                merchant.id,
                embedding_vec,
            )
            merchant.embedding = embedding_vec
        except Exception as e:
            # Log but don't fail if embedding fails
            logger.warning("embedding_generation_failed", merchant_id=str(merchant.id), error=str(e))

        return MerchantResponse.model_validate(merchant)

    @transactional
    async def get_by_id(self, merchant_id: UUID) -> MerchantResponse:
        """
        Get merchant by ID.

        Args:
            merchant_id: UUID of merchant

        Returns:
            Merchant response

        Raises:
            ResourceNotFound: If merchant not found
        """
        merchant = await self._merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise ResourceNotFound(f"Merchant {merchant_id} not found")
        return MerchantResponse.model_validate(merchant)

    @transactional
    async def list_all(
        self, skip: int = 0, limit: int = 100
    ) -> MerchantListResponse:
        """
        List all merchants with pagination.

        Args:
            skip: Offset for pagination
            limit: Max results (capped at 500)

        Returns:
            Paginated merchant list
        """
        # Validate and cap limit
        if skip < 0:
            skip = 0
        if limit < 1:
            limit = 1
        if limit > 500:
            limit = 500

        merchants, total = await self._merchant_repo.list_all(skip, limit)
        return MerchantListResponse(
            items=[MerchantResponse.model_validate(m) for m in merchants],
            total=total,
            skip=skip,
            limit=limit,
        )

    @transactional
    async def update(
        self, merchant_id: UUID, request: MerchantUpdateRequest
    ) -> MerchantResponse:
        """
        Update a merchant.

        Args:
            merchant_id: UUID of merchant
            request: Update request with optional fields

        Returns:
            Updated merchant response

        Raises:
            ResourceNotFound: If merchant not found
        """
        merchant = await self._merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise ResourceNotFound(f"Merchant {merchant_id} not found")

        # Track if name changed for embedding regeneration
        name_changed = request.name and request.name != merchant.name

        # Update fields
        if request.name:
            merchant.name = request.name
        if request.logo_url is not None:
            merchant.logo_url = request.logo_url
        if request.weight is not None:
            merchant.weight = request.weight
        if request.metadata is not None:
            merchant.metadata = request.metadata

        merchant = await self._merchant_repo.update(
            merchant.id,
            name=merchant.name,
            logo_url=merchant.logo_url,
            weight=merchant.weight,
            metadata=merchant.metadata,
        )

        # Regenerate embedding if name changed
        if name_changed:
            try:
                embedding_vec = await self._llm.embed(merchant.name)
                await store_embedding(
                    "merchant",
                    merchant.id,
                    embedding_vec,
                )
                merchant.embedding = embedding_vec
            except Exception as e:
                logger.warning("embedding_regeneration_failed", merchant_id=str(merchant.id), error=str(e))

        return MerchantResponse.model_validate(merchant)

    @transactional
    async def delete(self, merchant_id: UUID) -> bool:
        """
        Soft delete a merchant.

        Args:
            merchant_id: UUID of merchant

        Returns:
            True if deleted, False if not found
        """
        merchant = await self._merchant_repo.get_by_id(merchant_id)
        if not merchant:
            return False

        await self._merchant_repo.delete(merchant_id)
        return True

    @transactional
    async def bulk_create(
        self, requests: list[MerchantCreateRequest]
    ) -> list[MerchantResponse]:
        """
        Create multiple merchants in a batch.

        Args:
            requests: List of merchant creation requests

        Returns:
            List of created merchant responses
        """
        merchants = []
        for request in requests:
            try:
                response = await self.create(request)
                merchants.append(response)
            except AppException:
                # Skip duplicates or invalid merchants
                continue

        return merchants

    @transactional
    async def search_by_similarity(
        self, query: str, threshold: float = 0.7, limit: int = 10
    ) -> list[tuple[MerchantResponse, float]]:
        """
        Search merchants by embedding similarity.

        Args:
            query: Text query
            threshold: Similarity threshold (0-1)
            limit: Max results

        Returns:
            List of (merchant, similarity_score) tuples
        """
        # Generate embedding for query
        query_embedding = await self._llm.embed(query)

        # Search by similarity
        results = await search_embeddings_by_similarity(
            query_embedding, "merchant", threshold, limit
        )

        # Fetch merchant details for each result
        merchant_results = []
        for embedding, score in results:
            merchant = await self._merchant_repo.get_by_id(embedding.resource_id)
            if merchant:
                merchant_results.append(
                    (MerchantResponse.model_validate(merchant), score)
                )

        return merchant_results

    @transactional
    async def assign_mcc(self, merchant_id: UUID, mcc_id: UUID) -> dict:
        """
        Assign an MCC to a merchant.

        Args:
            merchant_id: UUID of merchant
            mcc_id: UUID of MCC

        Returns:
            Join record details

        Raises:
            ResourceNotFound: If merchant or MCC not found
        """
        merchant = await self._merchant_repo.get_by_id(merchant_id)
        if not merchant:
            raise ResourceNotFound(f"Merchant {merchant_id} not found")

        mcc = await self._mcc_repo.get_by_id(mcc_id)
        if not mcc:
            raise ResourceNotFound(f"MCC {mcc_id} not found")

        join_record = await self._mcc_repo.add_merchant_to_mcc(mcc_id, merchant_id)
        return {
            "merchant_id": str(merchant_id),
            "mcc_id": str(mcc_id),
            "created_at": join_record.created_at.isoformat(),
        }
