"""Interactive setup wizard — `cadre init`."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from cadre import __version__
from cadre.config import (
    AgentConfig,
    CadreConfig,
    ProjectConfig,
    ProviderConfig,
    TeamConfig,
    ToolsConfig,
    WorkflowsConfig,
)
from cadre.detect import detect_project

console = Console()

# Model strategies with agent assignments and estimated cost per task
STRATEGIES = {
    "balanced": {
        "description": "Opus lead, Sonnet team (~$0.28/task)",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "anthropic/claude-sonnet-4-6",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "anthropic/claude-sonnet-4-6",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "quality": {
        "description": "Opus design, Sonnet code (~$0.45/task)",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "anthropic/claude-opus-4-6",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "anthropic/claude-sonnet-4-6",
            "solo": "anthropic/claude-opus-4-6",
        },
    },
    "cost": {
        "description": "Sonnet lead, Haiku team (~$0.09/task)",
        "agents": {
            "lead": "anthropic/claude-sonnet-4-6",
            "architect": "anthropic/claude-haiku-4-5-20251001",
            "engineer": "anthropic/claude-haiku-4-5-20251001",
            "qa": "anthropic/claude-haiku-4-5-20251001",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "mixed": {
        "description": "Best model per provider per role (recommended)",
        "agents": {
            "lead": "anthropic/claude-opus-4-6",
            "architect": "openai/o3",
            "engineer": "anthropic/claude-sonnet-4-6",
            "qa": "openai/gpt-4o",
            "solo": "anthropic/claude-sonnet-4-6",
        },
    },
    "local": {
        "description": "Ollama only, free (~$0.00/task)",
        "agents": {
            "lead": "ollama/llama3.3-70b",
            "architect": "ollama/llama3.3-70b",
            "engineer": "ollama/llama3.3-70b",
            "qa": "ollama/llama3.3-70b",
            "solo": "ollama/llama3.3-70b",
        },
    },
}


def run_init(output_path: Path | None = None) -> CadreConfig:
    """Run the interactive setup wizard."""
    if output_path is None:
        output_path = Path("cadre.yml")

    console.print(Panel(f"[bold]OpenCadre v{__version__}[/bold]", style="blue"))
    console.print()

    # Auto-detect project
    detection = detect_project()
    for detail in detection.details:
        console.print(f"  [dim]{detail}[/dim]")
    if detection.details:
        console.print()

    # Project name
    default_name = detection.project_name or Path.cwd().name
    project_name = Prompt.ask("Project name", default=default_name)

    # Project type
    project_type = detection.project_type
    if project_type == "generic":
        project_type = Prompt.ask(
            "Project type",
            choices=["dbt", "generic"],
            default="generic",
        )

    # Warehouse
    warehouse = detection.warehouse or "snowflake"
    if project_type == "dbt" and not detection.warehouse:
        warehouse = Prompt.ask(
            "Warehouse",
            choices=["snowflake", "bigquery", "redshift", "postgres", "databricks", "duckdb"],
            default="snowflake",
        )

    # Providers
    console.print("\n[bold]LLM Providers[/bold]")
    providers: dict[str, ProviderConfig] = {}
    for provider in detection.detected_providers:
        console.print(f"  [green]✓[/green] {provider} (API key detected)")
        providers[provider] = ProviderConfig()

    if not providers:
        console.print("  [yellow]No API keys detected in environment.[/yellow]")
        console.print("  Set ANTHROPIC_API_KEY, OPENAI_API_KEY, etc. or add them to cadre.yml")
        providers["anthropic"] = ProviderConfig()

    # Team mode
    console.print()
    mode = Prompt.ask(
        "Team mode",
        choices=["full", "solo"],
        default="full",
    )

    # Model strategy
    console.print("\n[bold]Model strategy:[/bold]")
    for name, strategy in STRATEGIES.items():
        console.print(f"  {name:10s} — {strategy['description']}")
    console.print()
    strategy_name = Prompt.ask(
        "Strategy",
        choices=list(STRATEGIES.keys()),
        default="balanced",
    )
    strategy = STRATEGIES[strategy_name]

    # Build agent configs
    agent_names = ["solo"] if mode == "solo" else ["lead", "architect", "engineer", "qa"]
    agents = {
        name: AgentConfig(model=strategy["agents"].get(name, "anthropic/claude-sonnet-4-6"))
        for name in agent_names
    }

    # Build config
    config = CadreConfig(
        project=ProjectConfig(
            name=project_name,
            type=project_type,
            warehouse=warehouse,
            ci_platform=detection.ci_platform,
        ),
        providers=providers,
        team=TeamConfig(mode=mode, agents=agents),
        tools=ToolsConfig(),
        workflows=WorkflowsConfig(),
    )

    # Save
    config.save(output_path)
    console.print(f"\n  [green]✓[/green] Written {output_path}")
    console.print("\n  Run [bold]cadre up[/bold] to start your team.")
    console.print("  Run [bold]cadre models[/bold] to see model benchmarks.\n")

    return config
