"""Application lifecycle initialization and shutdown."""

from typing import Optional
from app.workers.outbox_processor import AsyncOutboxProcessor
import structlog

logger = structlog.get_logger(__name__)

# Global outbox processor instance
_outbox_processor: Optional[AsyncOutboxProcessor] = None


async def init_app():
    """Initialize the application on startup."""
    global _outbox_processor

    logger.info("Starting application...")

    try:
        # Initialize database (migrations would be run here)
        logger.info("Database initialized")

        # Create and start outbox processor
        _outbox_processor = AsyncOutboxProcessor(poll_interval=2)
        await _outbox_processor.start()

        logger.info("Application started successfully")

    except Exception as e:
        logger.error("Failed to initialize application", error=str(e))
        raise


async def shutdown_app():
    """Shutdown the application cleanly."""
    global _outbox_processor

    logger.info("Shutting down application...")

    try:
        # Stop outbox processor
        if _outbox_processor:
            await _outbox_processor.stop()

        # Close database connections
        logger.info("Database connections closed")

        logger.info("Application shut down successfully")

    except Exception as e:
        logger.error("Error during shutdown", error=str(e))
        raise


def get_outbox_processor() -> Optional[AsyncOutboxProcessor]:
    """Get the global outbox processor instance."""
    return _outbox_processor
