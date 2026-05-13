"""MCC business logic service."""

from uuid import UUID
from typing import Optional
from app.core.context import transactional
from app.core.exceptions import AppException, ResourceNotFound
from app.models.mcc import Mcc, Category
from app.models.embedding import Embedding
from app.repositories.mcc_repository import MccRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.schemas import (
    MccCreateRequest,
    MccUpdateRequest,
    MccResponse,
    MccListResponse,
    CategoryCreateRequest,
    CategoryResponse,
)
from app.providers.llm.interface import ILlmProvider
from app.providers.embedding import store_embedding, search_embeddings_by_similarity


class MccService:
    """Service for MCC (Merchant Category Code) operations."""

    def __init__(
        self,
        llm_provider: ILlmProvider,
        mcc_repo: Optional[MccRepository] = None,
        embedding_repo: Optional[EmbeddingRepository] = None,
    ):
        """
        Initialize service with dependencies.

        Args:
            llm_provider: LLM provider for embeddings
            mcc_repo: MCC repository (uses DI if None)
            embedding_repo: Embedding repository (uses DI if None)
        """
        self._llm = llm_provider
        self._mcc_repo = mcc_repo or MccRepository()
        self._embedding_repo = embedding_repo or EmbeddingRepository()

    @transactional
    async def create(self, request: MccCreateRequest) -> MccResponse:
        """
        Create a new MCC.

        Args:
            request: MCC creation request

        Returns:
            Created MCC response

        Raises:
            AppException: If MCC code already exists
        """
        # Check code uniqueness
        existing = await self._mcc_repo.get_by_code(request.code)
        if existing:
            raise AppException(
                f"MCC code '{request.code}' already exists",
                status_code=409,
            )

        # Create MCC record
        mcc = Mcc(
            code=request.code,
            description=request.description,
            category_id=request.category_id,
        )
        mcc = await self._mcc_repo.create(mcc)

        # Generate embedding for description
        try:
            embedding_vec = await self._llm.embed(mcc.description)
            await store_embedding(
                "mcc",
                mcc.id,
                embedding_vec,
            )
            mcc.embedding = embedding_vec
        except Exception as e:
            print(f"Warning: Failed to generate embedding for MCC {mcc.id}: {e}")

        return MccResponse.model_validate(mcc)

    @transactional
    async def get_by_id(self, mcc_id: UUID) -> MccResponse:
        """
        Get MCC by ID.

        Args:
            mcc_id: UUID of MCC

        Returns:
            MCC response

        Raises:
            ResourceNotFound: If MCC not found
        """
        mcc = await self._mcc_repo.get_by_id(mcc_id)
        if not mcc:
            raise ResourceNotFound(f"MCC {mcc_id} not found")
        return MccResponse.model_validate(mcc)

    @transactional
    async def get_by_code(self, code: str) -> MccResponse:
        """
        Get MCC by code.

        Args:
            code: MCC code (e.g., "5411")

        Returns:
            MCC response

        Raises:
            ResourceNotFound: If MCC not found
        """
        mcc = await self._mcc_repo.get_by_code(code)
        if not mcc:
            raise ResourceNotFound(f"MCC code '{code}' not found")
        return MccResponse.model_validate(mcc)

    @transactional
    async def list_all(self, skip: int = 0, limit: int = 100) -> MccListResponse:
        """
        List all MCCs with pagination.

        Args:
            skip: Offset for pagination
            limit: Max results

        Returns:
            Paginated MCC list
        """
        if skip < 0:
            skip = 0
        if limit < 1:
            limit = 1
        if limit > 500:
            limit = 500

        mccs, total = await self._mcc_repo.list_all(skip, limit)
        return MccListResponse(
            items=[MccResponse.model_validate(m) for m in mccs],
            total=total,
            skip=skip,
            limit=limit,
        )

    @transactional
    async def update(self, mcc_id: UUID, request: MccUpdateRequest) -> MccResponse:
        """
        Update an MCC.

        Args:
            mcc_id: UUID of MCC
            request: Update request

        Returns:
            Updated MCC response

        Raises:
            ResourceNotFound: If MCC not found
        """
        mcc = await self._mcc_repo.get_by_id(mcc_id)
        if not mcc:
            raise ResourceNotFound(f"MCC {mcc_id} not found")

        # Track if description changed for embedding regeneration
        desc_changed = request.description and request.description != mcc.description

        # Update fields
        if request.description:
            mcc.description = request.description
        if request.category_id is not None:
            mcc.category_id = request.category_id

        mcc = await self._mcc_repo.update(mcc.id, **vars(mcc))

        # Regenerate embedding if description changed
        if desc_changed:
            try:
                embedding_vec = await self._llm.embed(mcc.description)
                await store_embedding(
                    "mcc",
                    mcc.id,
                    embedding_vec,
                )
                mcc.embedding = embedding_vec
            except Exception as e:
                print(f"Warning: Failed to regenerate embedding for MCC {mcc.id}: {e}")

        return MccResponse.model_validate(mcc)

    @transactional
    async def delete(self, mcc_id: UUID) -> bool:
        """
        Soft delete an MCC.

        Args:
            mcc_id: UUID of MCC

        Returns:
            True if deleted, False if not found
        """
        mcc = await self._mcc_repo.get_by_id(mcc_id)
        if not mcc:
            return False

        await self._mcc_repo.delete(mcc_id)
        return True

    @transactional
    async def search_by_similarity(
        self, query: str, threshold: float = 0.7, limit: int = 10
    ) -> list[tuple[MccResponse, float]]:
        """
        Search MCCs by embedding similarity.

        Args:
            query: Text query
            threshold: Similarity threshold (0-1)
            limit: Max results

        Returns:
            List of (MCC, similarity_score) tuples
        """
        # Generate embedding for query
        query_embedding = await self._llm.embed(query)

        # Search by similarity
        results = await search_embeddings_by_similarity(
            query_embedding, "mcc", threshold, limit
        )

        # Fetch MCC details for each result
        mcc_results = []
        for embedding, score in results:
            mcc = await self._mcc_repo.get_by_id(embedding.resource_id)
            if mcc:
                mcc_results.append((MccResponse.model_validate(mcc), score))

        return mcc_results

    @transactional
    async def create_category(self, request: CategoryCreateRequest) -> CategoryResponse:
        """
        Create a new category.

        Args:
            request: Category creation request

        Returns:
            Created category response

        Raises:
            AppException: If category name already exists
        """
        # Check name uniqueness
        existing = await self._mcc_repo.get_category_by_name(request.name)
        if existing:
            raise AppException(
                f"Category '{request.name}' already exists",
                status_code=409,
            )

        # Create category
        category = Category(
            name=request.name,
            description=request.description,
        )
        category = await self._mcc_repo.create_category(category)
        return CategoryResponse.model_validate(category)

    @transactional
    async def get_category_by_id(self, category_id: UUID) -> CategoryResponse:
        """
        Get category by ID.

        Args:
            category_id: UUID of category

        Returns:
            Category response

        Raises:
            ResourceNotFound: If category not found
        """
        category = await self._mcc_repo.get_category_by_id(category_id)
        if not category:
            raise ResourceNotFound(f"Category {category_id} not found")
        return CategoryResponse.model_validate(category)

    @transactional
    async def list_categories(self) -> list[CategoryResponse]:
        """
        List all categories.

        Returns:
            List of category responses
        """
        categories = await self._mcc_repo.list_categories()
        return [CategoryResponse.model_validate(c) for c in categories]
