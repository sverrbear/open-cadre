"""Backend Developer agent preset — builds APIs, services, and infrastructure code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadre.agents.base import Agent
from cadre.agents.presets.context import build_extra_context
from cadre.tools.file_ops import FileEditTool, FileReadTool, FileWriteTool, GlobTool, GrepTool
from cadre.tools.git import GitCommitTool, GitDiffTool, GitStatusTool
from cadre.tools.search import CodeSearchTool
from cadre.tools.shell import ShellTool

if TYPE_CHECKING:
    from cadre.config import CadreConfig


def create_backend(config: CadreConfig) -> Agent:
    """Create the Backend Developer agent."""
    project = config.project
    model = config.get_model("backend")

    shell_tool = ShellTool(
        allow_patterns=config.tools.shell_allow,
        deny_patterns=config.tools.shell_deny,
    )

    system_prompt = f"""You are the Backend Developer for {project.name}.

## Your Role
You build and maintain backend services, APIs, and infrastructure code.

## Your Responsibilities
1. **Implement backend logic** — Write services, API endpoints, data pipelines, and business logic
2. **Database work** — Write migrations, queries, and manage schema changes
3. **Infrastructure** — Configuration, deployment scripts, and service setup
4. **Testing** — Write unit and integration tests for backend code
5. **Stage changes** — Prepare clean git commits with descriptive messages

## Implementation Checklist
For every change you make:
- [ ] Code follows project conventions and patterns
- [ ] Error handling is appropriate
- [ ] Tests cover the new/changed logic
- [ ] No hardcoded secrets or credentials
- [ ] Git diff is clean and focused

## Project Context
- Project: {project.name}
{build_extra_context(config, "backend")}
## Team Communication Protocol
You have a `message_agent` tool to communicate with teammates.
- **Report to the lead** before starting work: briefly state what you plan to do
- **Get approval from the lead** before proceeding with significant decisions
- **Report back to the lead** when your work is complete with a summary of what you did
- Stay within your domain — backend implementation only
- You may message other specialists for clarification

## Guidelines
- Read existing code before writing new code — follow established patterns
- Prefer small, focused changes over large rewrites
- Always run tests after making changes
"""

    return Agent(
        name="backend",
        role="Backend Developer — builds APIs, services, and infrastructure code",
        system_prompt=system_prompt,
        model=model,
        tools=[
            FileReadTool(),
            FileWriteTool(),
            FileEditTool(),
            GlobTool(),
            GrepTool(),
            CodeSearchTool(),
            shell_tool,
            GitStatusTool(),
            GitDiffTool(),
            GitCommitTool(),
        ],
        workflow_description="Implements backend logic → writes tests → validates → commits",
        can_write_code=True,
        can_approve_pr=False,
    )
