"""Auto-creation pipeline API router."""

from typing import Optional, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import require_hmac_auth
from app.core.dependencies import get_pipeline_engine
from app.pipeline.engine import PipelineEngine
from app.pipeline.base_step import PipelineContext
from app.schemas import PipelineResultResponse, ValidationResultResponse
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/merchants", tags=["auto-creation"])


class AutoCreateRequest(BaseModel):
    """Request to auto-create a merchant via pipeline."""
    name: str
    provider: str = "auto_created"
    description: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class ValidateMerchantRequest(BaseModel):
    """Request to validate merchant data."""
    name: str
    provider: str = "auto_created"
    mcc_codes: Optional[list[str]] = None


@router.post(
    "/auto-create",
    response_model=PipelineResultResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hmac_auth)],
)
async def auto_create_merchant(
    body: AutoCreateRequest,
    engine: PipelineEngine = Depends(get_pipeline_engine),
) -> PipelineResultResponse:
    """
    Auto-create a merchant using the 7-step pipeline.

    Pipeline steps:
    1. Check if merchant already exists
    2. Research merchant via LLM/Tavily
    3. Generate embedding for merchant name
    4. Optionally enrich with Google Places data
    5. Classify merchant MCC via LLM
    6. Create merchant record
    7. Notify downstream services

    Returns:
    - 201 on success
    - 400 on validation error
    - 409 on conflict (merchant exists)
    """
    try:
        # Create pipeline context
        context = PipelineContext(
            data={
                "name": body.name,
                "provider": body.provider,
                "description": body.description,
                "raw_data": body.raw_data or {},
            }
        )

        start_time = datetime.utcnow()

        # Run auto-creation pipeline
        result = await engine.run("AUTO_CREATION", context)

        duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )

        # Extract steps completed and errors
        steps_completed = list(result.context.step_results.keys())
        errors = [str(e) for e in result.errors] if result.errors else []

        # Check if merchant was created
        merchant = result.context.get("merchant")
        merchant_id = result.context.get("merchant_id")

        if result.status == "success" and merchant_id:
            return PipelineResultResponse(
                merchant_id=merchant_id,
                steps_completed=steps_completed,
                errors=errors,
                status="success",
                duration_ms=duration_ms,
            )
        elif result.status == "partial" and merchant_id:
            return PipelineResultResponse(
                merchant_id=merchant_id,
                steps_completed=steps_completed,
                errors=errors,
                status="partial",
                duration_ms=duration_ms,
            )
        else:
            logger.error(
                "Pipeline execution failed",
                status=result.status,
                errors=errors,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Pipeline failed: {', '.join(errors)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Auto-create request failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.post(
    "/validate",
    response_model=ValidationResultResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def validate_merchant_data(
    body: ValidateMerchantRequest,
    engine: PipelineEngine = Depends(get_pipeline_engine),
) -> ValidationResultResponse:
    """
    Validate merchant data using the validation pipeline.

    Validation steps:
    1. Validate merchant name format
    2. Verify MCC codes exist
    3. Check for duplicates

    Returns:
    - valid: True if all validations pass
    - errors: List of validation errors
    """
    try:
        # Create pipeline context
        context = PipelineContext(
            data={
                "name": body.name,
                "provider": body.provider,
                "mcc_codes": body.mcc_codes or [],
            }
        )

        # Run validation pipeline
        result = await engine.run("VALIDATION", context)

        errors = []
        if result.errors:
            errors = [str(e) for e in result.errors]

        return ValidationResultResponse(
            valid=(result.status == "success"),
            errors=errors,
        )

    except Exception as e:
        logger.error("Validation request failed", error=str(e))
        return ValidationResultResponse(
            valid=False,
            errors=[str(e)],
        )
