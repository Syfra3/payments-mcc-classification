"""Pipeline step registry and execution type enums."""

from enum import Enum
from typing import Dict, List, Tuple, Type


class ExecutionType(str, Enum):
    """Execution type for pipeline steps."""

    BLOCKING = "blocking"  # Sequential, participates in transaction
    NON_BLOCKING = "non_blocking"  # Fire-and-forget, asyncio task


# Global step registry
# Key: (registry_name, order)
# Value: list of step classes
_STEP_REGISTRY: Dict[str, List[Tuple[int, Type]]] = {}


def register_step(registry: str, order: int, step_class: Type) -> None:
    """Register a step in the registry."""
    if registry not in _STEP_REGISTRY:
        _STEP_REGISTRY[registry] = []
    _STEP_REGISTRY[registry].append((order, step_class))
    # Sort by order
    _STEP_REGISTRY[registry].sort(key=lambda x: x[0])


def get_steps(registry: str) -> List[Tuple[int, Type]]:
    """Get all steps for a registry, sorted by order."""
    return _STEP_REGISTRY.get(registry, [])


def get_registry_names() -> List[str]:
    """Get all available registry names."""
    return list(_STEP_REGISTRY.keys())


def clear_registry() -> None:
    """Clear the entire registry (for testing)."""
    _STEP_REGISTRY.clear()
