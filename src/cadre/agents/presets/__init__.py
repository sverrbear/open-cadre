"""Preset agent definitions for the data team."""

from cadre.agents.presets.analytics_engineer import create_engineer
from cadre.agents.presets.data_architect import create_architect
from cadre.agents.presets.qa_engineer import create_qa
from cadre.agents.presets.solo import create_solo
from cadre.agents.presets.team_lead import create_lead

PRESET_FACTORIES = {
    "lead": create_lead,
    "architect": create_architect,
    "engineer": create_engineer,
    "qa": create_qa,
    "solo": create_solo,
}

__all__ = [
    "PRESET_FACTORIES",
    "create_architect",
    "create_engineer",
    "create_lead",
    "create_qa",
    "create_solo",
]
