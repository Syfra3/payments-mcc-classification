"""MCC classification step."""

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.decorators import step
from app.providers.llm.interface import ILlmProvider
from app.repositories.mcc_repository import MccRepository
from app.core.dependencies import get_llm_provider


@step(
    registry="AUTO_CREATION",
    order=5,
    execution_type="blocking",
    timeout_seconds=20,
    description="Classify merchant MCC via LLM",
)
class MccClassificationStep(BaseStep):
    """Step 5: Classify merchant's MCC (Merchant Category Code) via LLM."""

    def __init__(self):
        """Initialize step with dependencies."""
        super().__init__()
        try:
            self._llm = get_llm_provider()
        except Exception:
            self._llm = None
        self._mcc_repo = MccRepository()

    def should_run(self, context: PipelineContext) -> bool:
        """Only run if merchant not already found and LLM is available."""
        merchant_exists = context.get("merchant") is not None
        mcc_codes = context.get("mcc_codes")
        return not merchant_exists and not mcc_codes and self._llm is not None

    async def execute(self, context: PipelineContext) -> dict:
        """
        Classify merchant MCC using LLM.

        Args:
            context: Pipeline context with 'name' and optional 'description' fields

        Returns:
            Dict with mcc_code and confidence
        """
        if not self._llm:
            self._logger.warning("LLM provider not available for MCC classification")
            return {
                "mcc_classified": False,
                "error": "llm_unavailable",
                "mcc_codes": [],
            }

        merchant_name = context.get("name")
        description = context.get("description", merchant_name)

        if not merchant_name:
            return {
                "mcc_classified": False,
                "error": "no_name",
                "mcc_codes": [],
            }

        try:
            # Prompt LLM for MCC classification
            prompt = f"""
Classify the following merchant into appropriate MCC (Merchant Category Code) categories.
Merchant: {merchant_name}
Description: {description}

Provide your response as a simple list of MCC codes (e.g., "5411,5412").
Only include valid MCC codes.
"""
            mcc_response = await self._llm.generate(prompt, max_tokens=100, temperature=0.3)

            # Parse response as comma-separated codes
            mcc_codes = [c.strip() for c in mcc_response.split(",") if c.strip()]

            # Verify MCCs exist in DB
            valid_mccs = []
            for code in mcc_codes:
                mcc = await self._mcc_repo.get_by_code(code)
                if mcc:
                    valid_mccs.append(code)

            if valid_mccs:
                context.set("mcc_codes", valid_mccs)
                self._logger.info(
                    "MCC classification successful",
                    merchant_name=merchant_name,
                    mcc_codes=valid_mccs,
                )
                return {
                    "mcc_classified": True,
                    "mcc_codes": valid_mccs,
                    "confidence": 0.8,
                }
            else:
                self._logger.warning(
                    "No valid MCCs found from LLM response",
                    merchant_name=merchant_name,
                    response=mcc_response,
                )
                return {
                    "mcc_classified": False,
                    "reason": "no_valid_mccs",
                    "mcc_codes": [],
                }
        except Exception as e:
            self._logger.error(
                "MCC classification failed",
                merchant_name=merchant_name,
                error=str(e),
            )
            return {
                "mcc_classified": False,
                "error": str(e),
                "mcc_codes": [],
            }
