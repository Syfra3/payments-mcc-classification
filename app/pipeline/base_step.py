"""Base class for all pipeline steps."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


class PipelineContext:
    """Context object passed through pipeline steps."""

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None,
        **kwargs,
    ):
        """Initialize pipeline context."""
        self._data = data or {}
        self._data.update(kwargs)
        self.session = session
        self.step_results: Dict[str, Any] = {}
        self.start_time = datetime.utcnow()
        self.cancelled = False
        self._logger = logger

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context data."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in context data."""
        self._data[key] = value

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to context data."""
        if name.startswith("_") or name in ("session", "step_results", "start_time", "cancelled"):
            return object.__getattribute__(self, name)
        return self._data.get(name)

    def log(self, level: str, msg: str, **kwargs) -> None:
        """Log a message with context."""
        getattr(self._logger, level.lower())(msg, **kwargs)


class BaseStep(ABC):
    """Base class for all pipeline steps."""

    def __init__(self):
        """Initialize base step."""
        self._logger = structlog.get_logger(self.__class__.__name__)

    def should_run(self, context: PipelineContext) -> bool:
        """
        Determine if this step should run.

        Override in subclasses to conditionally skip execution.
        """
        return True

    @abstractmethod
    async def execute(self, context: PipelineContext) -> Any:
        """
        Execute the step logic.

        Must be implemented by subclasses.
        """
        raise NotImplementedError

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get step metadata (registry, order, execution_type, timeout)."""
        return {
            "registry": getattr(cls, "__step_registry__", None),
            "order": getattr(cls, "__step_order__", None),
            "execution_type": getattr(cls, "__execution_type__", None),
            "timeout": getattr(cls, "__step_timeout__", None),
        }
