"""Pipeline execution engine."""

import asyncio
from typing import Dict, List, Tuple, Type, Any
import structlog

from app.pipeline.base_step import BaseStep, PipelineContext
from app.pipeline.registry import get_steps, ExecutionType

logger = structlog.get_logger(__name__)


class PipelineEngine:
    """Executes pipeline steps in sequence or parallel based on execution type."""

    async def run(self, registry: str, context: PipelineContext) -> PipelineContext:
        """
        Run all steps in a registry.

        Steps are executed in order. BLOCKING steps are awaited sequentially.
        NON_BLOCKING steps are gathered at the end.

        Args:
            registry: Name of the registry to run
            context: Pipeline context to pass through steps

        Returns:
            The modified context after all steps have run
        """
        steps = get_steps(registry)

        if not steps:
            logger.warning(f"No steps registered for registry: {registry}")
            return context

        non_blocking_tasks: List[asyncio.Task] = []
        max_timeout = 0

        for order, step_cls in steps:
            # Instantiate the step
            step_instance: BaseStep = step_cls()

            # Check if step should run
            try:
                should_run = step_instance.should_run(context)
            except Exception as e:
                logger.error(
                    f"Error checking should_run for {step_cls.__name__}",
                    error=str(e),
                )
                should_run = True

            if not should_run:
                logger.debug(f"Skipping step: {step_cls.__name__}")
                continue

            # Get step metadata
            metadata = step_instance.get_metadata()
            execution_type = metadata.get("execution_type", ExecutionType.BLOCKING)
            timeout = metadata.get("timeout")

            if timeout:
                max_timeout = max(max_timeout, timeout)

            logger.info(
                f"Executing step",
                step=step_cls.__name__,
                registry=registry,
                order=order,
                execution_type=execution_type,
            )

            try:
                if execution_type == ExecutionType.NON_BLOCKING:
                    # Create non-blocking task
                    task = asyncio.create_task(
                        self._run_step(step_instance, step_cls.__name__, context, timeout)
                    )
                    non_blocking_tasks.append(task)
                else:
                    # Execute blocking step
                    await self._run_step(step_instance, step_cls.__name__, context, timeout)

            except Exception as e:
                logger.error(
                    f"Error executing step {step_cls.__name__}: {e}",
                    step=step_cls.__name__,
                    error=str(e),
                )
                # For blocking steps, re-raise the exception
                if execution_type == ExecutionType.BLOCKING:
                    raise

        # Wait for all non-blocking tasks
        if non_blocking_tasks:
            # Add a buffer to the timeout
            gather_timeout = max_timeout + 10 if max_timeout else None
            try:
                await asyncio.gather(*non_blocking_tasks, timeout=gather_timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Non-blocking tasks timed out after {gather_timeout}s")
            except Exception as e:
                logger.error(f"Error in non-blocking tasks: {e}", error=str(e))

        return context

    async def _run_step(
        self,
        step_instance: BaseStep,
        step_name: str,
        context: PipelineContext,
        timeout: int | None,
    ) -> None:
        """Run a single step with timeout handling."""
        try:
            if timeout:
                await asyncio.wait_for(step_instance.execute(context), timeout=timeout)
            else:
                await step_instance.execute(context)

            logger.info(f"Step completed: {step_name}")
            context.step_results[step_name] = {"status": "success"}

        except asyncio.TimeoutError:
            logger.warning(f"Step {step_name} timed out after {timeout}s")
            context.step_results[step_name] = {"status": "timeout", "timeout": timeout}
            raise

        except Exception as e:
            logger.error(f"Step {step_name} failed: {e}", error=str(e))
            context.step_results[step_name] = {"status": "failed", "error": str(e)}
            raise
