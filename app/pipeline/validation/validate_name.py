"""Validate merchant name step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.core.exceptions import ValidationError


@step(
    registry="VALIDATION",
    order=1,
    execution_type="blocking",
    timeout_seconds=5,
    description="Validate merchant name format and length",
)
class ValidateNameStep(BaseStep):
    """Step 1: Validate merchant name format and length."""

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if name is provided."""
        return context.get("name") is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Validate merchant name per business rules.

        Args:
            context: Pipeline context with 'name' field

        Returns:
            Dict with validation result

        Raises:
            ValidationError: If name is invalid
        """
        name = context.get("name")

        # Check empty
        if not name or not isinstance(name, str):
            raise ValidationError("Merchant name must be a non-empty string")

        # Check length
        if len(name.strip()) == 0:
            raise ValidationError("Merchant name cannot be whitespace only")

        if len(name) < 1:
            raise ValidationError("Merchant name must be at least 1 character")

        if len(name) > 255:
            raise ValidationError("Merchant name must be at most 255 characters")

        # Check for invalid characters (basic)
        invalid_chars = ["<", ">", "{", "}", "|", "\\", "^", "`"]
        if any(char in name for char in invalid_chars):
            raise ValidationError("Merchant name contains invalid characters")

        self._logger.info(
            "Merchant name validated",
            name=name,
            length=len(name),
        )
        return {"name_valid": True, "length": len(name)}
