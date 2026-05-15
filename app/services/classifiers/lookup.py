"""Lookup table classifier for direct MCC lookups."""

from typing import Optional
import structlog
from app.services.classifiers.base import IClassifier, ClassificationResult
from app.services.classifiers.exceptions import ClassificationError
from app.repositories.mcc_repository import MccRepository

logger = structlog.get_logger(__name__)


class LookupTableClassifier(IClassifier):
    """Direct lookup classifier that uses MCC database without inference.

    MVP implementation for extensibility. Does not perform any inference.
    """

    def __init__(self):
        """Initialize with MCC repository."""
        self._mcc_repo = MccRepository()

    async def classify(
        self,
        merchant_name: str,
        tenant_id: str,
        description: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a merchant using direct MCC lookup.

        Note: This implementation does not use merchant_name for matching.
        It's a placeholder for future direct merchant->MCC mapping.

        Args:
            merchant_name: Name of the merchant (not used in MVP)
            tenant_id: Tenant context for scoping
            description: Optional merchant description (not used)

        Returns:
            ClassificationResult with default category and 0.0 confidence

        Raises:
            ClassificationError: If input is invalid
        """
        # Input validation
        if not merchant_name or not isinstance(merchant_name, str):
            raise ClassificationError("merchant_name cannot be empty")

        if not tenant_id or not isinstance(tenant_id, str):
            raise ClassificationError("tenant_id cannot be empty")

        logger.info(
            "LookupTableClassifier invoked (MVP returns default)",
            merchant_name=merchant_name,
            tenant_id=tenant_id,
        )

        # MVP: Return default category with low confidence
        # In Phase 2, this would look up merchant by name in the database
        return ClassificationResult(
            category="OTROS",
            confidence=0.0,
            classifier_type="lookup",
            reasoning="Lookup table classifier not yet implemented",
            metadata={
                "merchant_name": merchant_name,
                "tenant_id": tenant_id,
            },
        )
