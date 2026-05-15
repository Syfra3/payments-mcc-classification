"""LLM-based merchant classifier using OpenAI."""

from typing import Optional
import structlog
from app.services.classifiers.base import IClassifier, ClassificationResult
from app.services.classifiers.exceptions import (
    ClassificationServiceError,
    TenantNotFoundError,
    ClassificationError,
)
from app.providers.llm.interface import ILlmProvider
from app.repositories.mcc_repository import CategoryRepository
from app.core.dependencies import get_llm_provider

logger = structlog.get_logger(__name__)


class LLMClassifier(IClassifier):
    """LLM-based classifier using OpenAI to classify merchants.

    Wraps existing OpenAI integration and returns results in ClassificationResult format.
    """

    def __init__(self, llm_provider: Optional[ILlmProvider] = None):
        """Initialize with LLM provider."""
        self._llm = llm_provider or get_llm_provider()
        self._category_repo = CategoryRepository()

    async def classify(
        self,
        merchant_name: str,
        tenant_id: str,
        description: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a merchant using OpenAI LLM.

        Args:
            merchant_name: Name of the merchant
            tenant_id: Tenant context for category scoping
            description: Optional merchant description

        Returns:
            ClassificationResult with category and confidence from LLM

        Raises:
            ClassificationError: If input is invalid
            TenantNotFoundError: If tenant has no categories
            ClassificationServiceError: If LLM API fails
        """
        # Input validation
        if not merchant_name or not isinstance(merchant_name, str):
            raise ClassificationError("merchant_name cannot be empty")

        if not tenant_id or not isinstance(tenant_id, str):
            raise ClassificationError("tenant_id cannot be empty")

        # Verify tenant has categories
        tenant_categories = await self._category_repo.list_all(tenant_id)
        if not tenant_categories:
            raise TenantNotFoundError(tenant_id)

        # Build category list for LLM context
        category_names = [cat.name for cat in tenant_categories]
        categories_str = ", ".join(category_names)

        try:
            # Build prompt for LLM
            prompt = f"""Classify the following merchant into one of these categories: {categories_str}

Merchant Name: {merchant_name}
Description: {description or merchant_name}

Respond with only the category name from the list above. Do not include any explanation."""

            # Call LLM
            response = await self._llm.generate(prompt, max_tokens=50, temperature=0.3)
            category = response.strip().upper()

            # Verify the category is valid
            if category not in category_names:
                # If LLM returned something not in the list, use the first category with low confidence
                logger.warning(
                    "LLM returned invalid category",
                    merchant_name=merchant_name,
                    response=category,
                    valid_categories=category_names,
                    tenant_id=tenant_id,
                )
                category = category_names[0] if category_names else "OTROS"
                confidence = 0.3
            else:
                confidence = 0.8  # High confidence for LLM responses

            return ClassificationResult(
                category=category,
                confidence=confidence,
                classifier_type="llm",
                reasoning=f"Classified by OpenAI LLM (model: {self._llm.model_name})",
                metadata={"merchant_name": merchant_name, "tenant_id": tenant_id},
            )

        except Exception as e:
            if isinstance(e, ClassificationError):
                raise
            logger.error(
                "LLM classification failed",
                merchant_name=merchant_name,
                tenant_id=tenant_id,
                error=str(e),
            )
            raise ClassificationServiceError(
                "openai",
                str(e),
                f"OpenAI classification failed for merchant '{merchant_name}'",
            )
