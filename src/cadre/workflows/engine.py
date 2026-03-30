"""Workflow execution engine."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from cadre.agents.base import AgentEvent
from cadre.workflows.types import WorkflowDef, WorkflowEvent

if TYPE_CHECKING:
    from cadre.orchestrator.router import MessageRouter
    from cadre.orchestrator.team import Team


class WorkflowEngine:
    """Executes multi-step workflows by routing instructions to agents."""

    def __init__(self, team: Team, router: MessageRouter) -> None:
        self.team = team
        self.router = router

    async def run(
        self, workflow: WorkflowDef, user_request: str
    ) -> AsyncIterator[WorkflowEvent | AgentEvent]:
        """Execute a workflow, yielding events as each step progresses."""
        context = user_request

        for i, step in enumerate(workflow.steps):
            # Check condition
            if step.condition and not self._evaluate_condition(step.condition, context):
                continue

            # Build prompt with accumulated context
            prompt = f"{step.instruction}\n\nContext:\n{context}"

            yield WorkflowEvent(
                type="step_start",
                agent=step.agent,
                instruction=step.instruction,
                step_index=i,
            )

            # Route message to agent and collect response
            response_text = ""
            async for event in self.router.send_to_agent(step.agent, prompt):
                yield event
                if isinstance(event, AgentEvent) and event.type == "response":
                    response_text = event.content

            yield WorkflowEvent(
                type="step_complete",
                agent=step.agent,
                content=response_text,
                step_index=i,
            )

            # Wait for approval if needed
            if step.wait_for_approval:
                yield WorkflowEvent(
                    type="approval_needed",
                    agent=step.agent,
                    content=response_text,
                    step_index=i,
                )
                # The UI layer handles getting user approval before continuing

            # Accumulate context for next step
            if step.pass_output_to_next and response_text:
                context = f"{context}\n\n{step.agent} output:\n{response_text}"

        yield WorkflowEvent(type="workflow_complete", content="Workflow finished")

    def _evaluate_condition(self, condition: str, context: str) -> bool:
        """Evaluate a simple condition against the current context."""
        # Simple keyword-based conditions for now
        # e.g., "risk_level:high" checks if "high" appears in context
        if ":" in condition:
            _key, value = condition.split(":", 1)
            return value.lower() in context.lower()
        return True
