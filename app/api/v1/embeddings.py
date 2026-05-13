"""Embedding search API router."""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.schemas import EmbeddingSearchRequest, EmbeddingSearchResponse
from app.core.auth import require_hmac_auth
from app.core.dependencies import get_llm_provider, get_merchant_service, get_mcc_service
from app.providers.embedding import search_embeddings_by_similarity
from app.services.merchant_service import MerchantService
from app.services.mcc_service import MccService

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/search",
    response_model=EmbeddingSearchResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def search_embeddings(
    body: EmbeddingSearchRequest,
    merchant_service: MerchantService = Depends(get_merchant_service),
    mcc_service: MccService = Depends(get_mcc_service),
) -> EmbeddingSearchResponse:
    """
    Search across merchants and MCCs by embedding similarity.

    - **query**: Search query text
    - **resource_types**: List of resource types to search ("merchant", "mcc")
    - **threshold**: Similarity threshold (0-1)
    - **limit**: Max results per resource type
    """
    try:
        response = EmbeddingSearchResponse(merchants=[], mccs=[])

        # Search merchants if requested
        if "merchant" in body.resource_types:
            try:
                merchant_results = await merchant_service.search_by_similarity(
                    body.query, body.threshold, body.limit
                )
                response.merchants = [
                    {
                        "merchant": {
                            "id": str(m.id),
                            "name": m.name,
                            "provider": m.provider,
                            "logo_url": m.logo_url,
                            "weight": m.weight,
                        },
                        "score": round(score, 4),
                    }
                    for m, score in merchant_results
                ]
            except Exception as e:
                # Log but continue searching other types
                print(f"Merchant search failed: {e}")

        # Search MCCs if requested
        if "mcc" in body.resource_types:
            try:
                mcc_results = await mcc_service.search_by_similarity(
                    body.query, body.threshold, body.limit
                )
                response.mccs = [
                    {
                        "mcc": {
                            "id": str(m.id),
                            "code": m.code,
                            "description": m.description,
                        },
                        "score": round(score, 4),
                    }
                    for m, score in mcc_results
                ]
            except Exception as e:
                # Log but continue
                print(f"MCC search failed: {e}")

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
