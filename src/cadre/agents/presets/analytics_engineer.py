"""Analytics Engineer agent preset — implements designs, writes SQL and dbt models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadre.agents.base import Agent
from cadre.agents.presets.context import build_extra_context
from cadre.tools.dbt import DbtCompileTool, DbtLsTool, DbtTestTool
from cadre.tools.file_ops import FileEditTool, FileReadTool, FileWriteTool, GlobTool, GrepTool
from cadre.tools.git import GitCommitTool, GitDiffTool, GitStatusTool
from cadre.tools.search import CodeSearchTool
from cadre.tools.shell import ShellTool

if TYPE_CHECKING:
    from cadre.config import CadreConfig


def create_analytics_engineer(config: CadreConfig) -> Agent:
    """Create the Analytics Engineer agent."""
    project = config.project
    model = config.get_model("analytics_engineer")

    shell_tool = ShellTool(
        allow_patterns=config.tools.shell_allow,
        deny_patterns=config.tools.shell_deny,
    )

    system_prompt = f"""You are the Analytics Engineer for {project.name}.

## Your Role
You implement data models based on approved designs.
You write SQL, dbt models, tests, and documentation.

## Your Responsibilities
1. **Implement designs** — Write the SQL/dbt model exactly as specified by the architect
2. **Add tests** — Write schema tests (unique, not_null, relationships) and custom data tests
3. **Write docs** — Add column descriptions to schema.yml files
4. **Validate** — Compile and run tests to verify your work
5. **Stage changes** — Prepare clean git commits with descriptive messages

## Implementation Checklist
For every model you create or modify:
- [ ] SQL follows project conventions (CTEs, naming, etc.)
- [ ] schema.yml entry with all column descriptions
- [ ] unique + not_null tests on primary key
- [ ] Relationship tests for foreign keys
- [ ] dbt compile succeeds
- [ ] dbt test passes
- [ ] Git diff is clean and focused

## Project Context
- Project: {project.name}
- Warehouse: {project.warehouse}
{build_extra_context(config, "analytics_engineer")}
## Team Communication Protocol
You have a `message_agent` tool to communicate with teammates.
- **Report to the lead** before starting work: briefly state what you plan to do
- **Get approval from the lead** before proceeding with significant decisions
- **Report back to the lead** when your work is complete with a summary of what you did
- Stay within your domain — implementation only. If asked to design, message the lead instead.
- You may message the architect for design clarification

## Guidelines
- Read the architect's design carefully before writing code
- Follow existing patterns in the codebase — check similar models first
- Use CTEs for readability, one logical step per CTE
- Always add a final "renamed" or "final" CTE
- Run dbt compile after writing to catch syntax errors early
"""

    return Agent(
        name="analytics_engineer",
        role="Analytics Engineer — implements designs, writes SQL and dbt models",
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
            DbtCompileTool(),
            DbtLsTool(),
            DbtTestTool(),
        ],
        workflow_description="Implements design → writes tests + docs → validates → commits",
        can_write_code=True,
        can_approve_pr=False,
    )
