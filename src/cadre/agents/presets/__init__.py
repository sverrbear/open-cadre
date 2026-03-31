"""Preset agent definitions for the team."""

from cadre.agents.presets.analytics_engineer import create_analytics_engineer
from cadre.agents.presets.backend import create_backend
from cadre.agents.presets.data_architect import create_data_architect
from cadre.agents.presets.frontend import create_frontend
from cadre.agents.presets.qa import create_qa
from cadre.agents.presets.qa_engineer import create_data_qa
from cadre.agents.presets.solo import create_solo
from cadre.agents.presets.team_lead import create_lead

PRESET_FACTORIES = {
    "lead": create_lead,
    "backend": create_backend,
    "frontend": create_frontend,
    "data_architect": create_data_architect,
    "analytics_engineer": create_analytics_engineer,
    "data_qa": create_data_qa,
    "qa": create_qa,
    "solo": create_solo,
}

# Descriptions for specialist agents (excludes lead and solo)
PRESET_DESCRIPTIONS = {
    "backend": "Backend development — APIs, services, infrastructure code",
    "frontend": "Frontend development — UI components, styling, client-side logic",
    "data_architect": "Data architecture — designs schemas, classifies risk, proposes grain/key",
    "analytics_engineer": "Analytics engineering — writes SQL, dbt models, tests, docs",
    "data_qa": "Data quality assurance — reviews data models against designs",
    "qa": "General QA — code review, test coverage, integration testing",
}

__all__ = [
    "PRESET_DESCRIPTIONS",
    "PRESET_FACTORIES",
    "create_analytics_engineer",
    "create_backend",
    "create_data_architect",
    "create_data_qa",
    "create_frontend",
    "create_lead",
    "create_qa",
    "create_solo",
]
