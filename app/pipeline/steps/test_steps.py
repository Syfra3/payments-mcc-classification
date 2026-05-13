"""Test steps for pipeline testing."""

from app.pipeline.decorators import step
from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.registry import ExecutionType


@step("test_registry", order=1, execution_type=ExecutionType.BLOCKING)
class TestStep1(BaseStep):
    """First test step."""

    async def execute(self, context: PipelineContext) -> None:
        """Execute test step 1."""
        context.set("step1_result", "completed")
        context.log("info", "TestStep1 executed")


@step("test_registry", order=2, execution_type=ExecutionType.BLOCKING)
class TestStep2(BaseStep):
    """Second test step."""

    async def execute(self, context: PipelineContext) -> None:
        """Execute test step 2."""
        step1_result = context.get("step1_result")
        context.set("step2_result", f"received: {step1_result}")
        context.log("info", "TestStep2 executed", step1_result=step1_result)


@step("test_registry", order=3, execution_type=ExecutionType.NON_BLOCKING)
class TestStep3NonBlocking(BaseStep):
    """Non-blocking test step."""

    async def execute(self, context: PipelineContext) -> None:
        """Execute test step 3 (non-blocking)."""
        import asyncio

        await asyncio.sleep(0.1)
        context.set("step3_result", "non_blocking_done")
        context.log("info", "TestStep3 executed (non-blocking)")


@step("conditional_registry", order=1, execution_type=ExecutionType.BLOCKING)
class ConditionalStep(BaseStep):
    """Step that conditionally runs."""

    def should_run(self, context: PipelineContext) -> bool:
        """Skip if 'skip_condition' is True."""
        return not context.get("skip_condition", False)

    async def execute(self, context: PipelineContext) -> None:
        """Execute conditional step."""
        context.set("conditional_result", "executed")
        context.log("info", "ConditionalStep executed")
