"""Merchant API router."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.schemas import (
    MerchantCreateRequest,
    MerchantUpdateRequest,
    MerchantResponse,
    MerchantListResponse,
)
from app.services.merchant_service import MerchantService
from app.core.dependencies import get_merchant_service
from app.core.auth import require_hmac_auth
from app.core.exceptions import ResourceNotFound, AppException

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post(
    "",
    response_model=MerchantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def create_merchant(
    body: MerchantCreateRequest,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """
    Create a new merchant.

    - **name**: Merchant name (required, 1-255 chars)
    - **provider**: Provider name (required)
    - **mcc_codes**: Optional list of MCC codes to assign
    - **logo_url**: Optional logo URL
    - **metadata**: Optional metadata dictionary
    """
    try:
        return await service.create(body)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{merchant_id}",
    response_model=MerchantResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def get_merchant(
    merchant_id: UUID,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Get a merchant by ID."""
    try:
        return await service.get_by_id(merchant_id)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get(
    "",
    response_model=MerchantListResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def list_merchants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantListResponse:
    """
    List all merchants with pagination.

    - **skip**: Offset for pagination (default: 0)
    - **limit**: Number of results (default: 100, max: 500)
    """
    return await service.list_all(skip, limit)


@router.patch(
    "/{merchant_id}",
    response_model=MerchantResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def update_merchant(
    merchant_id: UUID,
    body: MerchantUpdateRequest,
    service: MerchantService = Depends(get_merchant_service),
) -> MerchantResponse:
    """Update a merchant (partial update allowed)."""
    try:
        return await service.update(merchant_id, body)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{merchant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_hmac_auth)],
)
async def delete_merchant(
    merchant_id: UUID,
    service: MerchantService = Depends(get_merchant_service),
) -> None:
    """Soft delete a merchant."""
    deleted = await service.delete(merchant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Merchant not found")


@router.post(
    "/bulk/create",
    response_model=list[MerchantResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def bulk_create_merchants(
    requests: list[MerchantCreateRequest],
    service: MerchantService = Depends(get_merchant_service),
) -> list[MerchantResponse]:
    """Create multiple merchants in a batch."""
    return await service.bulk_create(requests)


@router.post(
    "/search/similarity",
    response_model=list[dict],
    dependencies=[Depends(require_hmac_auth)],
)
async def search_merchants_by_similarity(
    query: str = Query(..., min_length=1, max_length=1000),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    limit: int = Query(10, ge=1, le=100),
    service: MerchantService = Depends(get_merchant_service),
) -> list[dict]:
    """
    Search merchants by embedding similarity.

    - **query**: Search query text
    - **threshold**: Similarity threshold (0-1)
    - **limit**: Max results
    """
    results = await service.search_by_similarity(query, threshold, limit)
    return [
        {
            "merchant": MerchantResponse.model_validate(merchant).model_dump(),
            "score": score,
        }
        for merchant, score in results
    ]


@router.post(
    "/{merchant_id}/mcc/{mcc_id}",
    response_model=dict,
    dependencies=[Depends(require_hmac_auth)],
)
async def assign_mcc_to_merchant(
    merchant_id: UUID,
    mcc_id: UUID,
    service: MerchantService = Depends(get_merchant_service),
) -> dict:
    """Assign an MCC to a merchant."""
    try:
        return await service.assign_mcc(merchant_id, mcc_id)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
