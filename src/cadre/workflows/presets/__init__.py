"""Preset workflow definitions."""

from cadre.workflows.presets.code_review import code_review
from cadre.workflows.presets.design_implement_review import design_implement_review
from cadre.workflows.presets.model_creation import model_creation

PRESET_WORKFLOWS = {
    "design-implement-review": design_implement_review,
    "code-review": code_review,
    "model-creation": model_creation,
}

__all__ = ["PRESET_WORKFLOWS", "code_review", "design_implement_review", "model_creation"]
