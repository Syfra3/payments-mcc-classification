"""Base interfaces and data structures for classification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from app.services.classifiers.exceptions import ClassificationError


@dataclass
class ClassificationResult:
    """Result of a classification operation."""

    category: str  # Category name (e.g., "FARMACIA")
    confidence: float  # 0.0 to 1.0
    classifier_type: str  # "llm" | "rules" | "lookup"
    reasoning: Optional[str] = None  # Why this category was chosen
    metadata: Optional[Dict[str, Any]] = None  # Additional context

    def __post_init__(self):
        """Validate result fields."""
        if not self.category or not isinstance(self.category, str):
            raise ValueError("category must be a non-empty string")

        if not isinstance(self.confidence, (int, float)):
            raise ValueError("confidence must be a number")

        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        if self.classifier_type not in ("llm", "rules", "lookup"):
            raise ValueError("classifier_type must be one of: 'llm', 'rules', 'lookup'")

        if self.reasoning is not None and not isinstance(self.reasoning, str):
            raise ValueError("reasoning must be a string or None")

        if self.metadata is None:
            self.metadata = {}


class IClassifier(ABC):
    """Abstract base class for all classifier implementations.

    Classifiers implement pluggable strategies for merchant classification.
    All operations must be tenant-scoped; cross-tenant data must never be returned.
    """

    @abstractmethod
    async def classify(
        self,
        merchant_name: str,
        tenant_id: str,
        description: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a merchant name into a category.

        Args:
            merchant_name: Name of the merchant to classify (non-empty string)
            tenant_id: Tenant context for isolation (non-empty string)
            description: Optional merchant description for additional context

        Returns:
            ClassificationResult with category, confidence, and classifier_type

        Raises:
            ClassificationError: If merchant_name is empty or None
            TenantNotFoundError: If tenant_id does not exist or has no configuration
            ClassificationServiceError: If classification fails due to external service failure
        """
        # Validate inputs
        if not merchant_name or not isinstance(merchant_name, str):
            raise ClassificationError("merchant_name cannot be empty")

        if not tenant_id or not isinstance(tenant_id, str):
            raise ClassificationError("tenant_id cannot be empty")

        pass
