"""Workflow type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """A single step in a workflow — assigns an instruction to an agent."""

    agent: str
    instruction: str
    wait_for_approval: bool = False
    pass_output_to_next: bool = True
    condition: str | None = None


@dataclass
class WorkflowDef:
    """Definition of a multi-step workflow."""

    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> WorkflowDef:
        """Create a WorkflowDef from a YAML config dict."""
        steps = []
        for step_data in data.get("steps", []):
            steps.append(
                WorkflowStep(
                    agent=step_data["agent"],
                    instruction=step_data["instruction"],
                    wait_for_approval=step_data.get("wait_for_approval", False),
                    pass_output_to_next=step_data.get("pass_output_to_next", True),
                    condition=step_data.get("condition"),
                )
            )
        return cls(
            name=name,
            description=data.get("description", ""),
            steps=steps,
        )


@dataclass
class WorkflowEvent:
    """Event emitted during workflow execution."""

    type: str  # "step_start", "step_complete", "approval_needed", "workflow_complete", "error"
    agent: str = ""
    instruction: str = ""
    content: str = ""
    step_index: int = 0
