"""LangFuse tracing client."""

from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

# LangFuse client is optional - will be initialized on first use
_client = None


def get_langfuse():
    """Get or initialize the LangFuse client."""
    global _client

    if _client is not None:
        return _client

    try:
        from langfuse import Langfuse
        from app.core.config import settings

        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            logger.warning("LangFuse credentials not configured, tracing disabled")
            return None

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_url,
        )
        logger.info(f"LangFuse client initialized at {settings.langfuse_url}")
        return _client

    except ImportError:
        logger.warning("langfuse package not installed, tracing disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize LangFuse: {e}")
        return None


def create_trace(name: str, metadata: Optional[Dict[str, Any]] = None):
    """Create a LangFuse trace."""
    client = get_langfuse()
    if client is None:
        return None

    try:
        return client.trace(name=name, metadata=metadata or {})
    except Exception as e:
        logger.warning(f"Failed to create trace: {e}")
        return None
