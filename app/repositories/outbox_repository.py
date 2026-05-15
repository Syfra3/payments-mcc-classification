"""Outbox event repository for reliable event delivery."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.embedding import OutboxEvent
from app.core.context import get_session


class OutboxRepository:
    """Repository for OutboxEvent entity."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize with optional session."""
        self.session = session

    def _get_session(self) -> AsyncSession:
        """Get the current session from context or parameter."""
        session = self.session or get_session()
        if not session:
            raise RuntimeError("No database session available")
        return session

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Create and persist an outbox event."""
        session = self._get_session()
        session.add(event)
        await session.flush()
        return event

    async def get_by_id(self, event_id: UUID) -> Optional[OutboxEvent]:
        """Get outbox event by ID."""
        session = self._get_session()
        stmt = select(OutboxEvent).where(OutboxEvent.id == event_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending(self, limit: int = 100) -> List[OutboxEvent]:
        """List pending outbox events ready for delivery."""
        session = self._get_session()
        stmt = (
            select(OutboxEvent)
            .where(
                and_(
                    OutboxEvent.status == "PENDING",
                    OutboxEvent.next_retry_at.is_(None) | (OutboxEvent.next_retry_at <= datetime.utcnow()),
                )
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        event_id: UUID,
        status: str,
        retry_count: int = 0,
        last_error: Optional[str] = None,
        delivered_at: Optional[datetime] = None,
    ) -> Optional[OutboxEvent]:
        """Update event status and metadata."""
        session = self._get_session()
        event = await self.get_by_id(event_id)
        if not event:
            return None

        event.status = status
        event.retry_count = retry_count
        if last_error:
            event.last_error = last_error
        if delivered_at:
            event.delivered_at = delivered_at

        await session.flush()
        return event

    async def mark_delivered(self, event_id: UUID) -> Optional[OutboxEvent]:
        """Mark event as delivered."""
        session = self._get_session()
        event = await self.get_by_id(event_id)
        if not event:
            return None

        event.status = "DELIVERED"
        event.delivered_at = datetime.utcnow()
        await session.flush()
        return event

    async def mark_failed(
        self, event_id: UUID, error: str, next_retry_at: datetime
    ) -> Optional[OutboxEvent]:
        """Mark event as failed and set next retry time."""
        session = self._get_session()
        event = await self.get_by_id(event_id)
        if not event:
            return None

        event.status = "FAILED"
        event.last_error = error
        event.next_retry_at = next_retry_at
        event.retry_count = (event.retry_count or 0) + 1
        await session.flush()
        return event

    async def mark_dead_lettered(self, event_id: UUID, error: str = None) -> Optional[OutboxEvent]:
        """Mark event as dead-lettered (permanent failure)."""
        session = self._get_session()
        event = await self.get_by_id(event_id)
        if not event:
            return None

        event.status = "DEAD_LETTERED"
        if error:
            event.last_error = error
        await session.flush()
        return event
