"""Solo agent preset — all-in-one agent that handles everything."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadre.agents.base import Agent
from cadre.tools.dbt import DbtCompileTool, DbtLsTool, DbtTestTool
from cadre.tools.file_ops import FileEditTool, FileReadTool, FileWriteTool, GlobTool, GrepTool
from cadre.tools.git import GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from cadre.tools.search import CodeSearchTool
from cadre.tools.shell import ShellTool

if TYPE_CHECKING:
    from cadre.config import CadreConfig


def create_solo(config: "CadreConfig") -> Agent:
    """Create the Solo agent — a single all-in-one agent."""
    project = config.project
    model = config.get_model("solo")

    shell_tool = ShellTool(
        allow_patterns=config.tools.shell_allow,
        deny_patterns=config.tools.shell_deny,
    )

    system_prompt = f"""You are a data engineering assistant for {project.name}.

## Your Role
You handle all data engineering tasks: design, implementation, testing, and review.

## Your Process
For any task, follow this process:
1. **Understand** — Read the request, explore existing code, understand context
2. **Design** — Propose the approach (grain, key, materialization) before writing code
3. **Implement** — Write the SQL/dbt model, tests, and docs
4. **Validate** — Compile, run tests, review your own work
5. **Deliver** — Stage clean git commits, summarize what you did

## Project Context
- Project: {project.name}
- Warehouse: {project.warehouse}

## Guidelines
- Always explore existing code before writing new code
- Follow established patterns in the project
- Ask for clarification when requirements are ambiguous
- Run dbt compile after writing SQL to catch errors early
- Add tests and docs for every model you create
"""

    return Agent(
        name="solo",
        role="Solo Agent — handles design, implementation, testing, and review",
        system_prompt=system_prompt,
        model=model,
        tools=[
            FileReadTool(), FileWriteTool(), FileEditTool(),
            GlobTool(), GrepTool(), CodeSearchTool(),
            shell_tool,
            GitStatusTool(), GitDiffTool(), GitCommitTool(), GitLogTool(),
            DbtCompileTool(), DbtLsTool(), DbtTestTool(),
        ],
        workflow_description="Understands → designs → implements → validates → delivers",
        can_write_code=True,
        can_approve_pr=True,
    )
