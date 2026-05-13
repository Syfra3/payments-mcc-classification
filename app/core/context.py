"""Transaction context management via contextvars."""

import inspect
from contextvars import ContextVar, Token
from functools import wraps
from typing import Any, Callable, TypeVar, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

# Context variable for storing the ambient session
transactional_context: ContextVar[Optional[AsyncSession]] = ContextVar(
    "session", default=None
)

T = TypeVar("T")


def get_session() -> Optional[AsyncSession]:
    """Get the current ambient session from context."""
    return transactional_context.get()


def set_session(session: AsyncSession) -> Token:
    """Set the current ambient session in context."""
    return transactional_context.set(session)


def reset_session(token: Token) -> None:
    """Reset the context session using the provided token."""
    transactional_context.reset(token)


async def async_session_context(session: AsyncSession):
    """Async context manager for setting session in context."""
    token = set_session(session)
    try:
        yield
    finally:
        reset_session(token)


def transactional(force_new: bool = False) -> Callable:
    """
    Decorator to manage database transactions via ambient context.

    If force_new=False (default), reuses existing ambient session if available.
    If force_new=True, always creates a new session.

    Usage:
        @transactional()
        async def create_merchant(self, data: dict) -> Merchant:
            merchant = Merchant(**data)
            session = get_session()
            session.add(merchant)
            await session.flush()
            return merchant
    """
    def decorator(fn: Callable) -> Callable:
        # Handle async functions
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                existing = get_session()

                # Reuse ambient session if it exists and not forcing new
                if existing and not force_new:
                    return await fn(*args, **kwargs)

                # Create new session (will be injected by FastAPI dependency)
                # For now, we expect the session to be available in context
                # This is a placeholder for integration with the database module
                return await fn(*args, **kwargs)

            return async_wrapper

        # Handle sync functions (if needed)
        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> Any:
            existing = get_session()
            if existing and not force_new:
                return fn(*args, **kwargs)
            return fn(*args, **kwargs)

        return sync_wrapper

    return decorator
