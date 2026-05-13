"""Step decorator for pipeline registration."""

from typing import Type, Optional
from app.pipeline.registry import register_step, ExecutionType


def step(
    registry: str,
    order: int,
    execution_type: ExecutionType = ExecutionType.BLOCKING,
    timeout: Optional[int] = 30,
):
    """
    Decorator to register a step class in the pipeline registry.

    Args:
        registry: Registry name to register this step under
        order: Execution order within the registry
        execution_type: Either BLOCKING or NON_BLOCKING
        timeout: Timeout in seconds (None for no timeout)

    Usage:
        @step("auto_creation", order=1, execution_type=ExecutionType.BLOCKING, timeout=30)
        class CheckExistenceStep(BaseStep):
            async def execute(self, context: PipelineContext) -> None:
                ...
    """

    def decorator(cls: Type) -> Type:
        # Validate that class has execute method
        if not hasattr(cls, "execute"):
            raise ValueError(f"Step class {cls.__name__} must have an async execute method")

        # Add metadata to the class
        cls.__step_registry__ = registry
        cls.__step_order__ = order
        cls.__execution_type__ = execution_type
        cls.__step_timeout__ = timeout

        # Register the step
        register_step(registry, order, cls)

        return cls

    return decorator
