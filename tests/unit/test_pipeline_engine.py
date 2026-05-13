"""Unit tests for pipeline engine and step framework."""
import asyncio
import pytest
from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.engine import PipelineEngine
from app.pipeline.decorators import step
from app.pipeline.registry import STEP_REGISTRY, ExecutionType


# ============================================================================
# Test Step Implementations
# ============================================================================


@step("test_registry", order=1, execution_type=ExecutionType.BLOCKING)
class TestStep1(BaseStep):
    """First test step - blocking."""

    async def execute(self, context: PipelineContext) -> None:
        context.state["step1_ran"] = True
        context.state["step1_data"] = "from_step1"


@step("test_registry", order=2, execution_type=ExecutionType.BLOCKING)
class TestStep2(BaseStep):
    """Second test step - blocking."""

    async def execute(self, context: PipelineContext) -> None:
        context.state["step2_ran"] = True
        context.state["step2_data"] = context.state.get("step1_data", "not_set")


@step("test_registry", order=3, execution_type=ExecutionType.NON_BLOCKING)
class TestStep3NonBlocking(BaseStep):
    """Third test step - non-blocking."""

    async def execute(self, context: PipelineContext) -> None:
        await asyncio.sleep(0.01)  # Small delay to show non-blocking
        context.state["step3_ran"] = True


@step("conditional_registry", order=1)
class ConditionalStep(BaseStep):
    """Step with conditional execution."""

    async def should_run(self, context: PipelineContext) -> bool:
        return context.state.get("run_conditional", False)

    async def execute(self, context: PipelineContext) -> None:
        context.state["conditional_ran"] = True


@step("error_registry", order=1)
class FailingStep(BaseStep):
    """Step that raises an error."""

    async def execute(self, context: PipelineContext) -> None:
        raise ValueError("Intentional test failure")


@step("timeout_registry", order=1)
class SlowStep(BaseStep):
    """Step that times out."""

    async def execute(self, context: PipelineContext) -> None:
        await asyncio.sleep(2.0)  # Sleep longer than timeout


# ============================================================================
# Test Cases
# ============================================================================


@pytest.mark.asyncio
async def test_step_registration():
    """Test that steps are registered correctly."""
    assert "test_registry" in STEP_REGISTRY
    assert len(STEP_REGISTRY["test_registry"]) >= 3
    # Find steps by name
    step_names = [step.__name__ for step in STEP_REGISTRY["test_registry"]]
    assert "TestStep1" in step_names
    assert "TestStep2" in step_names


@pytest.mark.asyncio
async def test_blocking_steps_execute_sequentially():
    """Test that blocking steps execute in order."""
    engine = PipelineEngine()
    ctx = PipelineContext()

    result = await engine.run("test_registry", ctx)

    assert result["status"] == "success"
    assert ctx.state.get("step1_ran") is True
    assert ctx.state.get("step2_ran") is True
    # Verify order: step2 should see data from step1
    assert ctx.state.get("step2_data") == "from_step1"


@pytest.mark.asyncio
async def test_should_run_skips_step():
    """Test that should_run() logic skips steps."""
    engine = PipelineEngine()
    ctx = PipelineContext(state={"run_conditional": False})

    result = await engine.run("conditional_registry", ctx)

    assert result["status"] == "success"
    assert ctx.state.get("conditional_ran") is None


@pytest.mark.asyncio
async def test_should_run_executes_when_true():
    """Test that should_run() executes when True."""
    engine = PipelineEngine()
    ctx = PipelineContext(state={"run_conditional": True})

    result = await engine.run("conditional_registry", ctx)

    assert result["status"] == "success"
    assert ctx.state.get("conditional_ran") is True


@pytest.mark.asyncio
async def test_exception_in_blocking_step_stops_pipeline():
    """Test that blocking step exception stops the pipeline."""
    engine = PipelineEngine()
    ctx = PipelineContext()

    # With asyncio.TimeoutError, execution should fail gracefully
    # But since we don't have a timeout set on this step, the exception should propagate
    result = await engine.run("error_registry", ctx)

    # Engine catches exceptions and returns failed status
    assert result["status"] == "failed"
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_pipeline_context_shares_state():
    """Test that context.state is shared across all steps."""
    engine = PipelineEngine()
    ctx = PipelineContext(state={"initial_value": "test"})

    result = await engine.run("test_registry", ctx)

    assert ctx.state.get("initial_value") == "test"  # Initial value preserved
    assert ctx.state.get("step1_ran") is True  # Added by step1
    assert ctx.state.get("step2_data") == "from_step1"  # Step2 saw step1's data


@pytest.mark.asyncio
async def test_step_execution_order():
    """Test that steps execute in order specified by decorator."""
    engine = PipelineEngine()
    ctx = PipelineContext(state={"execution_log": []})

    # Create steps with explicit order logging
    @step("order_test_registry", order=1)
    class OrderStep1(BaseStep):
        async def execute(self, context: PipelineContext) -> None:
            context.state["execution_log"].append(1)

    @step("order_test_registry", order=2)
    class OrderStep2(BaseStep):
        async def execute(self, context: PipelineContext) -> None:
            context.state["execution_log"].append(2)

    @step("order_test_registry", order=3)
    class OrderStep3(BaseStep):
        async def execute(self, context: PipelineContext) -> None:
            context.state["execution_log"].append(3)

    result = await engine.run("order_test_registry", ctx)

    assert result["status"] == "success"
    assert ctx.state["execution_log"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_empty_registry():
    """Test running empty registry returns success."""
    engine = PipelineEngine()
    ctx = PipelineContext()

    result = await engine.run("nonexistent_registry", ctx)

    assert result["status"] == "success"
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_pipeline_context_initialization():
    """Test PipelineContext initialization."""
    ctx = PipelineContext(
        input_data={"test": "value"},
        state={"key": "val"}
    )

    assert ctx.input_data == {"test": "value"}
    assert ctx.state == {"key": "val"}
    assert ctx.trace_id is not None


@pytest.mark.asyncio
async def test_pipeline_context_get_set():
    """Test PipelineContext get/set operations."""
    ctx = PipelineContext()

    ctx.set("key1", "value1")
    assert ctx.get("key1") == "value1"

    assert ctx.get("nonexistent") is None
    assert ctx.get("nonexistent", "default") == "default"
