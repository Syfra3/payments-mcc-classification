"""Validate MCC codes step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.repositories.mcc_repository import MccRepository
from app.core.exceptions import ValidationError


@step(
    registry="VALIDATION",
    order=2,
    execution_type="blocking",
    timeout_seconds=10,
    description="Verify MCC codes exist in database",
)
class ValidateMccStep(BaseStep):
    """Step 2: Verify that all provided MCC codes exist in the database."""

    def __init__(self):
        """Initialize step with MCC repository."""
        super().__init__()
        self._mcc_repo = MccRepository()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if mcc_codes are provided."""
        mcc_codes = context.get("mcc_codes")
        return mcc_codes and len(mcc_codes) > 0

    async def execute(self, context: PipelineContext) -> dict:
        """
        Verify MCC codes exist in database.

        Args:
            context: Pipeline context with 'mcc_codes' field

        Returns:
            Dict with validation result

        Raises:
            ValidationError: If any MCC code is not found
        """
        mcc_codes = context.get("mcc_codes", [])

        if not mcc_codes:
            return {"mcc_valid": True, "count": 0}

        # Check each MCC code
        invalid_codes = []
        for code in mcc_codes:
            mcc = await self._mcc_repo.get_by_code(code)
            if not mcc:
                invalid_codes.append(code)

        if invalid_codes:
            raise ValidationError(
                f"The following MCC codes do not exist: {', '.join(invalid_codes)}"
            )

        self._logger.info(
            "MCC codes validated",
            count=len(mcc_codes),
            codes=mcc_codes,
        )
        return {"mcc_valid": True, "count": len(mcc_codes), "codes": mcc_codes}
