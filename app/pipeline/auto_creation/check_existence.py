"""Check if merchant already exists step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.repositories.merchant_repository import MerchantRepository


@step(
    registry="AUTO_CREATION",
    order=1,
    execution_type="blocking",
    timeout_seconds=10,
    description="Check if merchant already exists",
)
class CheckExistenceStep(BaseStep):
    """Step 1: Check if a merchant with the same name already exists."""

    def __init__(self):
        """Initialize step."""
        super().__init__()
        self._merchant_repo = MerchantRepository()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant not already set."""
        return context.get("merchant") is None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Check for existing merchant by name.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with 'found' flag and optional 'merchant' data
        """
        merchant_name = context.get("name")
        if not merchant_name:
            self._logger.warning("No merchant name in context", merchant_name=merchant_name)
            return {"found": False, "reason": "no_name_provided"}

        # Query for existing merchant
        existing = await self._merchant_repo.get_by_name(merchant_name)
        if existing:
            context.set("merchant", existing)
            self._logger.info(
                "Merchant already exists",
                merchant_id=str(existing.id),
                merchant_name=merchant_name,
            )
            return {"found": True, "merchant_id": str(existing.id)}

        self._logger.info("No existing merchant found", merchant_name=merchant_name)
        return {"found": False}
