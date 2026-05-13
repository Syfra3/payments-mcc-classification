"""Outbox event API router."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from app.schemas import OutboxEventResponse, OutboxEventListResponse
from app.repositories.outbox_repository import OutboxRepository
from app.core.auth import require_hmac_auth
from app.core.exceptions import ResourceNotFound

router = APIRouter(prefix="/outbox", tags=["outbox"])


@router.get(
    "",
    response_model=OutboxEventListResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def list_outbox_events(
    status: str = Query("pending", regex="^(pending|delivered|failed)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    repo: OutboxRepository = Depends(lambda: OutboxRepository()),
) -> OutboxEventListResponse:
    """
    List outbox events with pagination.

    - **status**: Filter by event status (pending, delivered, failed)
    - **skip**: Offset for pagination
    - **limit**: Number of results (default: 100, max: 500)
    """
    events, total = await repo.list_all_by_status(status, skip, limit)
    return OutboxEventListResponse(
        items=[OutboxEventResponse.model_validate(e) for e in events],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{event_id}",
    response_model=OutboxEventResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def get_outbox_event(
    event_id: UUID,
    repo: OutboxRepository = Depends(lambda: OutboxRepository()),
) -> OutboxEventResponse:
    """Get a specific outbox event."""
    event = await repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return OutboxEventResponse.model_validate(event)


@router.post(
    "/{event_id}/retry",
    response_model=OutboxEventResponse,
    dependencies=[Depends(require_hmac_auth)],
)
async def retry_outbox_event(
    event_id: UUID,
    repo: OutboxRepository = Depends(lambda: OutboxRepository()),
) -> OutboxEventResponse:
    """Retry a failed outbox event."""
    event = await repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Reset event to pending for retry
    await repo.mark_pending(event_id)

    # Fetch updated event
    updated_event = await repo.get_by_id(event_id)
    return OutboxEventResponse.model_validate(updated_event)
