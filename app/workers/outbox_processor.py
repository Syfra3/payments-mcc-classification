"""Asynchronous outbox event processor for reliable event delivery."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.embedding import OutboxEvent
from app.core.database import async_session_factory
from app.repositories.outbox_repository import OutboxRepository
import structlog

logger = structlog.get_logger(__name__)

MAX_BACKOFF = 32.0
MAX_RETRIES = 6


class AsyncOutboxProcessor:
    """Asynchronous processor for outbox events with retry logic."""

    def __init__(self, poll_interval: int = 2):
        """
        Initialize the outbox processor.

        Args:
            poll_interval: Seconds between polling for pending events
        """
        self._poll_interval = poll_interval
        self._running = False
        self._tasks: set = set()
        self._outbox_repo = OutboxRepository()

    async def start(self):
        """Start the outbox processor as a background task."""
        self._running = True
        logger.info("Starting outbox processor", poll_interval=self._poll_interval)

        # Create and start the polling task
        task = asyncio.create_task(self._poll_loop())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def stop(self):
        """Stop the outbox processor and wait for pending tasks."""
        logger.info("Stopping outbox processor")
        self._running = False

        # Wait for all pending tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Outbox processor stopped")

    async def _poll_loop(self):
        """Main polling loop that fetches and processes events."""
        while self._running:
            try:
                await self._fetch_and_process_pending()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                logger.info("Outbox polling loop cancelled")
                break
            except Exception as e:
                logger.error("Error in polling loop", error=str(e))
                await asyncio.sleep(self._poll_interval)

    async def _fetch_and_process_pending(self):
        """Fetch pending events and process them."""
        async with async_session_factory() as session:
            try:
                # Query pending events with row-level locking for concurrency safety
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.status == "pending")
                    .order_by(OutboxEvent.created_at)
                    .limit(10)
                    .with_for_update(skip_locked=True)
                )

                events = result.scalars().all()

                if events:
                    logger.debug("Processing pending events", count=len(events))

                    # Process each event
                    for event in events:
                        task = asyncio.create_task(
                            self._process_event(event, session)
                        )
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)

                    # Wait for all event processing tasks with timeout
                    pending_tasks = [
                        t for t in self._tasks
                        if not t.done()
                    ]
                    if pending_tasks:
                        await asyncio.wait_for(
                            asyncio.gather(*pending_tasks, return_exceptions=True),
                            timeout=30.0,
                        )

                    # Commit after processing
                    await session.commit()

            except asyncio.TimeoutError:
                logger.warning("Event processing timeout")
                await session.rollback()
            except Exception as e:
                logger.error("Error fetching and processing pending events", error=str(e))
                await session.rollback()

    async def _process_event(self, event: OutboxEvent, session: AsyncSession):
        """
        Process a single outbox event.

        Args:
            event: The outbox event to process
            session: The database session
        """
        try:
            await self._dispatch(event)
            await self._outbox_repo.mark_delivered(event.id)
            logger.info(
                "Event processed successfully",
                event_id=str(event.id),
                event_type=event.event_type,
            )
        except Exception as e:
            await self._handle_event_error(event, str(e))
            logger.warning(
                "Event processing failed",
                event_id=str(event.id),
                event_type=event.event_type,
                error=str(e),
                retry_count=event.retry_count + 1,
            )

    async def _handle_event_error(self, event: OutboxEvent, error: str):
        """
        Handle event processing error with exponential backoff.

        Args:
            event: The outbox event
            error: The error message
        """
        retry_count = event.retry_count + 1

        if retry_count >= MAX_RETRIES:
            # Mark as dead lettered after max retries
            await self._outbox_repo.mark_dead_lettered(event.id, error)
            logger.error(
                "Event marked as dead lettered",
                event_id=str(event.id),
                retry_count=retry_count,
                error=error,
            )
        else:
            # Calculate next retry time with exponential backoff
            backoff = min(2 ** retry_count, MAX_BACKOFF)
            next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
            await self._outbox_repo.mark_failed(
                event.id, error, next_retry_at
            )
            logger.debug(
                "Event retry scheduled",
                event_id=str(event.id),
                retry_count=retry_count,
                backoff_seconds=backoff,
            )

    async def _dispatch(self, event: OutboxEvent):
        """
        Dispatch event to appropriate handler.

        Args:
            event: The outbox event to dispatch

        Raises:
            NotImplementedError: If no handler exists for event type
        """
        handlers = {
            "merchant.created": self._handle_merchant_created,
            "merchant.updated": self._handle_merchant_updated,
            "merchant.deleted": self._handle_merchant_deleted,
            "external_merchant.associated": self._handle_external_merchant_associated,
        }

        handler = handlers.get(event.event_type)
        if not handler:
            logger.warning(
                "No handler for event type",
                event_type=event.event_type,
            )
            return

        await handler(event)

    async def _handle_merchant_created(self, event: OutboxEvent):
        """
        Handle merchant created event.

        Args:
            event: The outbox event
        """
        payload = event.payload
        logger.info(
            "Handling merchant created event",
            merchant_id=payload.get("merchant_id"),
            merchant_name=payload.get("merchant_name"),
        )
        # Future: Call downstream services like voucher microservice
        # response = await self._voucher_client.notify_merchant_created(payload)

    async def _handle_merchant_updated(self, event: OutboxEvent):
        """
        Handle merchant updated event.

        Args:
            event: The outbox event
        """
        payload = event.payload
        logger.info(
            "Handling merchant updated event",
            merchant_id=payload.get("merchant_id"),
        )
        # Future: Call downstream services

    async def _handle_merchant_deleted(self, event: OutboxEvent):
        """
        Handle merchant deleted event.

        Args:
            event: The outbox event
        """
        payload = event.payload
        logger.info(
            "Handling merchant deleted event",
            merchant_id=payload.get("merchant_id"),
        )
        # Future: Call downstream services

    async def _handle_external_merchant_associated(self, event: OutboxEvent):
        """
        Handle external merchant associated event.

        Args:
            event: The outbox event
        """
        payload = event.payload
        logger.info(
            "Handling external merchant associated event",
            merchant_id=payload.get("merchant_id"),
            provider=payload.get("provider"),
        )
        # Future: Update related records
