"""MCC API router."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.schemas import (
    MccCreateRequest,
    MccUpdateRequest,
    MccResponse,
    MccListResponse,
    CategoryCreateRequest,
    CategoryResponse,
)
from app.services.mcc_service import MccService
from app.core.dependencies import get_mcc_service
from app.core.auth import require_hmac_auth
from app.core.exceptions import ResourceNotFound, AppException

router = APIRouter(prefix="/mccs", tags=["mccs"])


@router.post(
    "",
    response_model=MccResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def create_mcc(
    body: MccCreateRequest,
    service: MccService = Depends(get_mcc_service),
) -> MccResponse:
    """Create a new MCC."""
    try:
        return await service.create(body)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{mcc_id}",
    response_model=MccResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def get_mcc(
    mcc_id: UUID,
    service: MccService = Depends(get_mcc_service),
) -> MccResponse:
    """Get an MCC by ID."""
    try:
        return await service.get_by_id(mcc_id)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get(
    "",
    response_model=MccListResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def list_mccs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: MccService = Depends(get_mcc_service),
) -> MccListResponse:
    """List all MCCs with pagination."""
    return await service.list_all(skip, limit)


@router.get(
    "/code/{code}",
    response_model=MccResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def get_mcc_by_code(
    code: str,
    service: MccService = Depends(get_mcc_service),
) -> MccResponse:
    """Get an MCC by code."""
    try:
        return await service.get_by_code(code)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.patch(
    "/{mcc_id}",
    response_model=MccResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def update_mcc(
    mcc_id: UUID,
    body: MccUpdateRequest,
    service: MccService = Depends(get_mcc_service),
) -> MccResponse:
    """Update an MCC."""
    try:
        return await service.update(mcc_id, body)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{mcc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_hmac_auth)],
)
async def delete_mcc(
    mcc_id: UUID,
    service: MccService = Depends(get_mcc_service),
) -> None:
    """Soft delete an MCC."""
    deleted = await service.delete(mcc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MCC not found")


@router.post(
    "/search/similarity",
    response_model=list[dict],
    dependencies=[Depends(require_hmac_auth)],
)
async def search_mccs_by_similarity(
    query: str = Query(..., min_length=1, max_length=1000),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    limit: int = Query(10, ge=1, le=100),
    service: MccService = Depends(get_mcc_service),
) -> list[dict]:
    """Search MCCs by embedding similarity."""
    results = await service.search_by_similarity(query, threshold, limit)
    return [
        {
            "mcc": MccResponse.model_validate(mcc).model_dump(),
            "score": score,
        }
        for mcc, score in results
    ]


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def create_category(
    body: CategoryCreateRequest,
    service: MccService = Depends(get_mcc_service),
) -> CategoryResponse:
    """Create a new category."""
    try:
        return await service.create_category(body)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    dependencies=[Depends(require_hmac_auth)],
)
async def list_categories(
    service: MccService = Depends(get_mcc_service),
) -> list[CategoryResponse]:
    """List all categories."""
    return await service.list_categories()
