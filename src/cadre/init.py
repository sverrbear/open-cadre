"""Interactive setup — `cadre init`."""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from cadre import __version__
from cadre.config import (
    CADRE_DIR,
    AgentConfig,
    CadreConfig,
    ProjectConfig,
    ProviderConfig,
    TeamConfig,
    ToolsConfig,
    WorkflowsConfig,
)
from cadre.detect import detect_project
from cadre.keys import PROVIDER_DASHBOARDS, PROVIDER_ENV_VARS, generate_env_file, key_set

console = Console()

# Model strategies
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
        "description": "Best model per provider per role",
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


def run_init(base_path: Path | None = None) -> CadreConfig:
    """Run the interactive setup wizard. Creates .cadre/ directory."""
    if base_path is None:
        base_path = Path.cwd()

    cadre_dir = base_path / CADRE_DIR
    if cadre_dir.exists() and not Confirm.ask(
        f"  [yellow]{CADRE_DIR}/ already exists.[/yellow] Overwrite?"
    ):
        console.print("  Aborted.")
        raise SystemExit(0)

    from cadre.ui.logo import print_logo

    print_logo(console, version=__version__)
    console.print("[bold]Setup[/bold]")
    console.print()

    # --- Auto-detect ---
    detection = detect_project(base_path)
    if detection.details:
        for detail in detection.details:
            console.print(f"  [dim]{detail}[/dim]")
        console.print()

    # --- Project ---
    console.print("[bold]Project[/bold]")
    default_name = detection.project_name or base_path.name
    project_name = Prompt.ask("  Name", default=default_name)

    project_type = detection.project_type
    if project_type == "generic":
        project_type = Prompt.ask("  Type", choices=["dbt", "generic"], default="generic")
    else:
        console.print(f"  Type: [cyan]{project_type}[/cyan] (detected)")

    warehouse = detection.warehouse or "snowflake"
    if project_type == "dbt" and not detection.warehouse:
        warehouse = Prompt.ask(
            "  Warehouse",
            choices=["snowflake", "bigquery", "redshift", "postgres", "databricks", "duckdb"],
            default="snowflake",
        )
    elif detection.warehouse:
        console.print(f"  Warehouse: [cyan]{warehouse}[/cyan] (detected)")
    else:
        warehouse = Prompt.ask(
            "  Warehouse",
            choices=["snowflake", "bigquery", "redshift", "postgres", "databricks", "duckdb"],
            default="snowflake",
        )

    # --- API Keys ---
    console.print("\n[bold]API Keys[/bold]")
    console.print("  [dim]Keys are stored locally in cadre.env (gitignored).[/dim]\n")

    providers: dict[str, ProviderConfig] = {}
    entered_keys: dict[str, str] = {}
    for provider, env_var in PROVIDER_ENV_VARS.items():
        env_value = os.environ.get(env_var)
        if env_value:
            masked = env_value[:4] + "..." + env_value[-4:]
            console.print(f"  [green]✓[/green] {provider}: {masked} (from ${env_var})")
            providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
        else:
            if Confirm.ask(f"  Set up [bold]{provider}[/bold]?", default=False):
                dashboard_url = PROVIDER_DASHBOARDS.get(provider)
                if dashboard_url:
                    import webbrowser

                    console.print(f"  [dim]Opening {provider} dashboard...[/dim]")
                    webbrowser.open(dashboard_url)
                    console.print("  [dim]Create an API key and paste it below.[/dim]")
                key = Prompt.ask(f"  {provider} API key", default="", show_default=False)
                if key.strip():
                    entered_keys[provider] = key.strip()
                    key_set(base_path, provider=provider, value=key.strip())
                    providers[provider] = ProviderConfig(api_key=f"${{{env_var}}}")
                    console.print(f"  [green]✓[/green] {provider} configured")
                else:
                    console.print(f"  [dim]  Skipped {provider}[/dim]")

    if not providers:
        console.print("\n  [yellow]No API keys configured.[/yellow]")
        console.print("  You'll need at least one to use cadre.")
        console.print("  Run [bold]cadre keys set anthropic[/bold] after init.")
        providers["anthropic"] = ProviderConfig(api_key=f"${{{PROVIDER_ENV_VARS['anthropic']}}}")

    # --- Team ---
    console.print("\n[bold]Team[/bold]")
    mode = Prompt.ask("  Mode", choices=["full", "solo"], default="full")

    console.print("\n  [bold]Model strategies:[/bold]")
    for name, strategy in STRATEGIES.items():
        console.print(f"    {name:10s} — {strategy['description']}")
    strategy_name = Prompt.ask("\n  Strategy", choices=list(STRATEGIES.keys()), default="balanced")
    strategy = STRATEGIES[strategy_name]

    # Build agent configs
    agent_names = ["solo"] if mode == "solo" else ["lead", "architect", "engineer", "qa"]
    agents = {
        name: AgentConfig(model=strategy["agents"].get(name, "anthropic/claude-sonnet-4-6"))
        for name in agent_names
    }

    # Optional per-agent model customization
    if Confirm.ask("\n  Customize individual agent models?", default=False):
        console.print("  [dim]Enter a model (e.g. openai/gpt-4o) or press Enter to keep.[/dim]")
        for name in agent_names:
            current = agents[name].model
            custom = Prompt.ask(f"    {name}", default=current)
            if custom != current:
                agents[name] = AgentConfig(model=custom)
                provider = custom.split("/", 1)[0] if "/" in custom else None
                if provider and provider != "ollama":
                    env_var = PROVIDER_ENV_VARS.get(provider)
                    if env_var and not os.environ.get(env_var):
                        console.print(
                            f"    [yellow]No API key for {provider}. "
                            f"Run `cadre keys set {provider}` later.[/yellow]"
                        )

    # --- Build and save ---
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

    config.save(base_path)

    # Generate cadre.env with entered keys + placeholders
    generate_env_file(base_path, keys=entered_keys)

    # Ensure .cadre/ and cadre.env are in .gitignore
    _ensure_gitignored(base_path)

    # Print summary
    console.print(f"\n  [green]✓[/green] Created {CADRE_DIR}/config.yml")
    for name in agents:
        console.print(f"  [green]✓[/green] Created {CADRE_DIR}/agents/{name}.yml")
    console.print(f"  [green]✓[/green] Created {CADRE_DIR}/context.yml")
    console.print("  [green]✓[/green] Created cadre.env")

    has_keys = any(os.environ.get(v) for v in PROVIDER_ENV_VARS.values())
    console.print("\n  [bold]Next steps:[/bold]")
    if not has_keys:
        console.print("  1. Run [bold]cadre keys set anthropic[/bold] to add your API key")
        console.print("  2. Run [bold]cadre explore[/bold] to auto-configure agents")
        console.print("  3. Run [bold]cadre up[/bold] to start the TUI")
    else:
        console.print("  1. Run [bold]cadre explore[/bold] to auto-configure agents")
        console.print("  2. Run [bold]cadre up[/bold] to start the TUI")
    console.print()

    return config


def _ensure_gitignored(base_path: Path) -> None:
    """Make sure .cadre/ and cadre.env are listed in .gitignore."""
    from cadre.keys import ENV_FILE

    gitignore = base_path / ".gitignore"
    markers = [f"{CADRE_DIR}/", ENV_FILE]

    content = gitignore.read_text() if gitignore.exists() else ""
    missing = [m for m in markers if m not in content]
    if not missing:
        return

    if content and not content.endswith("\n"):
        content += "\n"
    for m in missing:
        content += f"{m}\n"
    gitignore.write_text(content)
