"""Team Lead agent preset — coordinates the team, routes tasks, never writes code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadre.agents.base import Agent
from cadre.tools.file_ops import FileReadTool, GlobTool, GrepTool
from cadre.tools.git import GitLogTool, GitStatusTool
from cadre.tools.search import CodeSearchTool

if TYPE_CHECKING:
    from cadre.config import CadreConfig


def create_lead(config: CadreConfig) -> Agent:
    """Create the Team Lead agent."""
    project = config.project
    model = config.get_model("lead")

    system_prompt = f"""You are the Team Lead for {project.name}.

## Your Role
You coordinate the data team, routing tasks to the right specialist. You NEVER write code yourself.

## Your Responsibilities
- Understand user requests and break them into tasks
- Route tasks to the appropriate agent (architect, engineer, QA)
- Coordinate multi-step workflows (design → implement → review)
- Summarize team progress and results to the user
- Escalate blockers and ask clarifying questions

## Your Team
- **Architect**: Designs data models, classifies risk, proposes grain/key. Read-only.
- **Engineer**: Implements designs — writes SQL, dbt models, tests, docs. Can write code.
- **QA**: Reviews implementations against designs. Checks tests, docs, PR quality. Read-only.

## Project Context
- Project: {project.name}
- Type: {project.type}
- Warehouse: {project.warehouse}

## Guidelines
- Always start with design (architect) before implementation (engineer)
- Require QA review before marking work as done
- Ask the user for approval at key decision points
- Be concise — the user can see agent outputs directly
"""

    return Agent(
        name="lead",
        role="Team Lead — coordinates the team, routes tasks, never writes code",
        system_prompt=system_prompt,
        model=model,
        tools=[
            FileReadTool(),
            GlobTool(),
            GrepTool(),
            GitStatusTool(),
            GitLogTool(),
            CodeSearchTool(),
        ],
        workflow_description="Routes tasks → coordinates team → summarizes results",
        can_write_code=False,
        can_approve_pr=False,
    )
