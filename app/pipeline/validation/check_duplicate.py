"""Check for duplicate merchant step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.repositories.merchant_repository import MerchantRepository
from app.core.exceptions import ValidationError


@step(
    registry="VALIDATION",
    order=3,
    execution_type="blocking",
    timeout_seconds=10,
    description="Verify merchant is not already registered",
)
class CheckDuplicateStep(BaseStep):
    """Step 3: Verify that the merchant is not already registered."""

    def __init__(self):
        """Initialize step with merchant repository."""
        super().__init__()
        self._merchant_repo = MerchantRepository()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if name is provided."""
        return context.get("name") is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Check for duplicate merchant by name + provider.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with duplicate check result

        Raises:
            ValidationError: If merchant already exists
        """
        merchant_name = context.get("name")
        provider = context.get("provider")

        if not merchant_name:
            return {"duplicate_checked": True, "is_duplicate": False}

        # Check by name (composite key with provider if provided)
        existing = await self._merchant_repo.get_by_name(merchant_name)
        if existing:
            # If provider is specified, check if it matches
            if provider and existing.provider != provider:
                self._logger.info(
                    "Merchant exists with different provider",
                    name=merchant_name,
                    existing_provider=existing.provider,
                    new_provider=provider,
                )
                return {"duplicate_checked": True, "is_duplicate": False}

            raise ValidationError(
                f"Merchant '{merchant_name}' already exists"
                + (f" with provider '{existing.provider}'" if existing.provider else "")
            )

        self._logger.info(
            "Merchant duplicate check passed",
            name=merchant_name,
        )
        return {"duplicate_checked": True, "is_duplicate": False}
