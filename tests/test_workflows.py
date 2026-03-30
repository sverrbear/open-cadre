"""Tests for workflow system."""

from __future__ import annotations

from cadre.workflows.presets import PRESET_WORKFLOWS
from cadre.workflows.types import WorkflowDef, WorkflowStep


def test_preset_workflows_exist():
    assert "design-implement-review" in PRESET_WORKFLOWS
    assert "code-review" in PRESET_WORKFLOWS
    assert "model-creation" in PRESET_WORKFLOWS


def test_design_implement_review():
    wf = PRESET_WORKFLOWS["design-implement-review"]
    assert len(wf.steps) == 3
    assert wf.steps[0].agent == "architect"
    assert wf.steps[0].wait_for_approval is True
    assert wf.steps[1].agent == "engineer"
    assert wf.steps[2].agent == "qa"


def test_workflow_from_dict():
    data = {
        "description": "Test workflow",
        "steps": [
            {"agent": "engineer", "instruction": "Do the thing"},
            {"agent": "qa", "instruction": "Check the thing", "wait_for_approval": True},
        ],
    }
    wf = WorkflowDef.from_dict("test", data)
    assert wf.name == "test"
    assert len(wf.steps) == 2
    assert wf.steps[1].wait_for_approval is True


def test_workflow_step_defaults():
    step = WorkflowStep(agent="test", instruction="do something")
    assert step.wait_for_approval is False
    assert step.pass_output_to_next is True
    assert step.condition is None
