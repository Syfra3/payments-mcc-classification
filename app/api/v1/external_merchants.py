"""External merchant API router."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from app.schemas import (
    ExternalMerchantCreateRequest,
    ExternalMerchantResponse,
    ExternalMerchantListResponse,
)
from app.services.external_merchant_service import ExternalMerchantService
from app.core.dependencies import get_external_merchant_service
from app.core.auth import require_hmac_auth
from app.core.exceptions import ResourceNotFound, AppException

router = APIRouter(prefix="/external-merchants", tags=["external-merchants"])


class AssociateMerchantRequest(BaseModel):
    """Request to associate external merchant with internal merchant."""
    merchant_id: UUID


@router.post(
    "",
    response_model=ExternalMerchantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def register_external_merchant(
    body: ExternalMerchantCreateRequest,
    service: ExternalMerchantService = Depends(get_external_merchant_service),
) -> ExternalMerchantResponse:
    """Register a new external merchant."""
    try:
        return await service.register(body)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{provider}/{provider_id}",
    response_model=ExternalMerchantResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def get_external_merchant(
    provider: str,
    provider_id: str,
    service: ExternalMerchantService = Depends(get_external_merchant_service),
) -> ExternalMerchantResponse:
    """Get an external merchant by provider and ID."""
    try:
        return await service.get_by_provider_id(provider, provider_id)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get(
    "",
    response_model=ExternalMerchantListResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def list_external_merchants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: ExternalMerchantService = Depends(get_external_merchant_service),
) -> ExternalMerchantListResponse:
    """List all external merchants with pagination."""
    return await service.list_all(skip, limit)


@router.post(
    "/{provider}/{provider_id}/associate",
    response_model=ExternalMerchantResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def associate_external_merchant(
    provider: str,
    provider_id: str,
    body: AssociateMerchantRequest,
    service: ExternalMerchantService = Depends(get_external_merchant_service),
) -> ExternalMerchantResponse:
    """Associate an external merchant with an internal merchant."""
    try:
        return await service.associate_merchant(provider, provider_id, body.merchant_id)
    except ResourceNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{provider}/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_hmac_auth)],
)
async def delete_external_merchant(
    provider: str,
    provider_id: str,
    service: ExternalMerchantService = Depends(get_external_merchant_service),
) -> None:
    """Soft delete an external merchant."""
    deleted = await service.delete(provider, provider_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"External merchant {provider}:{provider_id} not found",
        )
