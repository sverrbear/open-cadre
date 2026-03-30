"""CLI entry point — all `cadre` commands."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console

from cadre import __version__

if TYPE_CHECKING:
    from cadre.config import CadreConfig

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="cadre")
@click.pass_context
def main(ctx):
    """OpenCadre — Provider-agnostic AI team platform for data engineering."""
    from cadre.keys import load_env

    load_env()

    if ctx.invoked_subcommand is None:
        _launch_tui()


@main.command()
def init():
    """Interactive setup — creates .cadre/ config directory."""
    from cadre.init import run_init

    run_init()


@main.command()
@click.option("--model", "-m", default=None, help="Model to use for analysis")
def explore(model: str | None):
    """Explore codebase and auto-configure agents with AI."""
    from cadre.explore import run_explore

    run_explore(model=model)


@main.command()
def up():
    """Start the AI team and open the interactive TUI."""
    _launch_tui()


@main.command()
@click.argument("agent", required=False)
def chat(agent: str | None):
    """Chat with a specific agent (or the team lead)."""
    from cadre.orchestrator.router import MessageRouter
    from cadre.orchestrator.team import Team
    from cadre.ui.chat import ChatUI

    cfg = _load_config()
    if cfg is None:
        return

    team = Team(config=cfg)
    team.setup()
    router = MessageRouter(team=team)
    team.inject_router(router)
    chat_ui = ChatUI(router=router, console=console)

    if agent:
        if agent not in team.agents:
            console.print(
                f"[red]Agent '{agent}' not found.[/red] Available: {', '.join(team.agents.keys())}"
            )
            return
        console.print(f"[blue]Chatting with {agent}. Type /quit to exit.[/blue]\n")
    else:
        console.print("[blue]Chatting with the team. Type /quit to exit.[/blue]\n")

    asyncio.run(chat_ui.run_chat_loop())
    team.shutdown()


@main.command()
def status():
    """Show team and agent status."""
    from cadre.orchestrator.team import Team
    from cadre.ui.status import render_status

    cfg = _load_config()
    if cfg is None:
        return

    team = Team(config=cfg)
    team.setup()
    render_status(team, console)


@main.group(invoke_without_command=True)
@click.pass_context
def keys(ctx):
    """Manage API keys in cadre.env."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(keys_show)


@keys.command(name="show")
def keys_show():
    """Show configured API keys (masked)."""
    from cadre.keys import PROVIDER_DASHBOARDS, PROVIDER_ENV_VARS, show_keys

    console.print("[bold]API Keys[/bold]\n")
    key_status = show_keys()
    for provider, env_var in PROVIDER_ENV_VARS.items():
        masked = key_status.get(provider)
        if masked:
            console.print(f"  [green]✓[/green] {provider:12s} {masked}  ({env_var})")
        else:
            dashboard = PROVIDER_DASHBOARDS.get(provider, "")
            console.print(f"  [red]✗[/red] {provider:12s} not set    ({env_var})")
            if dashboard:
                console.print(f"    [dim]Get a key: {dashboard}[/dim]")
    console.print("\n  [dim]Keys are stored in cadre.env (gitignored).[/dim]")
    console.print("  [dim]Set a key: cadre keys set <provider>[/dim]\n")


@keys.command(name="set")
@click.argument("provider")
@click.argument("key_value", required=False)
def keys_set_cmd(provider: str, key_value: str | None):
    """Set an API key for a provider."""
    from cadre.keys import PROVIDER_ENV_VARS, key_set

    if provider not in PROVIDER_ENV_VARS:
        known = ", ".join(PROVIDER_ENV_VARS)
        console.print(f"[yellow]Unknown provider '{provider}'.[/yellow] Known: {known}")
        upper = provider.upper()
        console.print(f"[dim]Proceeding anyway — key will be saved as {upper}_API_KEY[/dim]")

    if key_value is None:
        key_value = click.prompt(f"  {provider} API key", hide_input=True)
    if not key_value.strip():
        console.print("[yellow]Empty key, nothing saved.[/yellow]")
        return

    key_set(provider=provider, value=key_value.strip())
    console.print(f"  [green]✓[/green] {provider} API key saved to cadre.env")


@keys.command(name="remove")
@click.argument("provider")
def keys_remove_cmd(provider: str):
    """Remove an API key from cadre.env."""
    from cadre.keys import key_remove

    key_remove(provider=provider)
    console.print(f"  [green]✓[/green] {provider} API key removed from cadre.env")


main.add_command(keys)


@main.group(invoke_without_command=True)
@click.pass_context
def models(ctx):
    """Show and manage model assignments."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(models_show)


@models.command(name="show")
def models_show():
    """Show current model assignments for each agent."""
    from cadre.keys import check_key_for_model

    cfg = _load_config()
    if cfg is None:
        return

    console.print("[bold]Model Assignments[/bold]\n")
    for name, agent_cfg in cfg.team.agents.items():
        status = "[green]enabled[/green]" if agent_cfg.enabled else "[red]disabled[/red]"
        has_key = check_key_for_model(agent_cfg.model)
        key_icon = "[green]✓[/green]" if has_key else "[yellow]⚠ no key[/yellow]"
        console.print(f"  {name:12s} {agent_cfg.model:40s} {status}  {key_icon}")
    console.print(f"\n  Team mode: {cfg.team.mode}")
    console.print()


@models.command(name="set")
@click.argument("agent")
@click.argument("model")
def models_set(agent: str, model: str):
    """Set the model for a specific agent.

    Example: cadre models set lead openai/gpt-4o
    """
    from cadre.keys import check_key_for_model, get_provider_for_model

    cfg = _load_config()
    if cfg is None:
        return

    if agent not in cfg.team.agents:
        available = ", ".join(cfg.team.agents.keys())
        console.print(f"[red]Agent '{agent}' not found.[/red] Available: {available}")
        return

    provider = get_provider_for_model(model)
    if provider and not check_key_for_model(model):
        console.print(f"[yellow]Warning: No API key found for '{provider}'.[/yellow]")
        console.print(f"  Run [bold]cadre keys set {provider}[/bold] to add it.\n")

    old_model = cfg.team.agents[agent].model
    cfg.team.agents[agent].model = model
    cfg.save()
    console.print(f"  [green]✓[/green] {agent}: {old_model} → {model}")


@models.command(name="list")
def models_list():
    """List available models from benchmarks."""
    from cadre.benchmarks.data import BenchmarkData

    bench = BenchmarkData()
    bench.render_table(console)
    console.print("\n  [dim]Any LiteLLM-compatible model string is accepted.[/dim]")
    console.print("  [dim]See https://docs.litellm.ai/docs/providers for all options.[/dim]\n")


@models.command(name="benchmarks")
def models_benchmarks():
    """Show model benchmarks and strategy recommendations."""
    from cadre.benchmarks.data import BenchmarkData

    bench = BenchmarkData()
    bench.render_table(console)
    console.print()
    bench.render_strategies(console)


@main.group()
def workflow():
    """Manage and run workflows."""
    pass


@workflow.command(name="list")
def workflow_list():
    """List available workflows."""
    from cadre.workflows.presets import PRESET_WORKFLOWS

    console.print("[bold]Available Workflows[/bold]\n")
    for name, wf in PRESET_WORKFLOWS.items():
        console.print(f"  [cyan]{name}[/cyan]")
        console.print(f"    {wf.description}")
        for i, step in enumerate(wf.steps, 1):
            approval = " [magenta](approval gate)[/magenta]" if step.wait_for_approval else ""
            console.print(f"    {i}. {step.agent}: {step.instruction[:80]}...{approval}")
        console.print()


@workflow.command(name="run")
@click.argument("name")
@click.argument("request", nargs=-1, required=True)
def workflow_run(name: str, request: tuple[str, ...]):
    """Run a specific workflow with a request."""
    from cadre.orchestrator.router import MessageRouter
    from cadre.orchestrator.team import Team
    from cadre.ui.chat import ChatUI
    from cadre.workflows.engine import WorkflowEngine
    from cadre.workflows.presets import PRESET_WORKFLOWS

    if name not in PRESET_WORKFLOWS:
        console.print(
            f"[red]Workflow '{name}' not found.[/red] "
            f"Available: {', '.join(PRESET_WORKFLOWS.keys())}"
        )
        return

    cfg = _load_config()
    if cfg is None:
        return

    team = Team(config=cfg)
    team.setup()
    router = MessageRouter(team=team)
    team.inject_router(router)
    engine = WorkflowEngine(team=team, router=router)
    chat_ui = ChatUI(router=router, console=console)

    user_request = " ".join(request)
    wf = PRESET_WORKFLOWS[name]

    console.print(f"[blue]Running workflow: {name}[/blue]")
    console.print(f"[dim]Request: {user_request}[/dim]\n")

    async def _run():
        async for event in engine.run(wf, user_request):
            if hasattr(event, "tool"):  # AgentEvent
                chat_ui.display_event(event)
            else:  # WorkflowEvent
                if event.type == "step_start":
                    console.print(f"\n[bold]→ {event.agent}[/bold]: {event.instruction}\n")
                elif event.type == "approval_needed":
                    from rich.prompt import Confirm

                    if not Confirm.ask("[magenta]Approve and continue?[/magenta]"):
                        console.print("[yellow]Workflow cancelled.[/yellow]")
                        return
                elif event.type == "workflow_complete":
                    console.print(f"\n[green]✓ {event.content}[/green]")

    asyncio.run(_run())
    team.shutdown()


@main.command()
def doctor():
    """Check prerequisites and configuration."""
    import os
    import shutil

    from cadre.config import CADRE_DIR

    console.print("[bold]OpenCadre Doctor[/bold]\n")

    # Check Python version
    py_version = sys.version_info
    if py_version >= (3, 10):
        console.print(
            f"  [green]✓[/green] Python {py_version.major}.{py_version.minor}.{py_version.micro}"
        )
    else:
        console.print(f"  [red]✗[/red] Python {py_version.major}.{py_version.minor} (need ≥3.10)")

    # Check config directory
    cadre_dir = Path.cwd() / CADRE_DIR
    if cadre_dir.exists():
        console.print(f"  [green]✓[/green] {CADRE_DIR}/ found")
        config_file = cadre_dir / "config.yml"
        if config_file.exists():
            console.print(f"  [green]✓[/green] {CADRE_DIR}/config.yml found")
        else:
            console.print(f"  [yellow]![/yellow] {CADRE_DIR}/config.yml missing")
        context_file = cadre_dir / "context.yml"
        if context_file.exists():
            console.print(f"  [green]✓[/green] {CADRE_DIR}/context.yml found")
        else:
            console.print(
                f"  [yellow]![/yellow] {CADRE_DIR}/context.yml missing — run `cadre explore`"
            )
    else:
        console.print(f"  [yellow]![/yellow] {CADRE_DIR}/ not found — run `cadre init`")

    # Check cadre.env
    from cadre.keys import ENV_FILE, PROVIDER_ENV_VARS

    env_path = Path.cwd() / ENV_FILE
    if env_path.exists():
        console.print(f"  [green]✓[/green] {ENV_FILE} found")
    else:
        console.print(
            f"  [yellow]![/yellow] {ENV_FILE} not found — run `cadre init` or `cadre keys set`"
        )

    # Check LLM providers
    found_providers = False
    for provider, env_var in PROVIDER_ENV_VARS.items():
        if os.environ.get(env_var):
            console.print(f"  [green]✓[/green] {provider} ({env_var})")
            found_providers = True

    if not found_providers:
        console.print("  [yellow]![/yellow] No API keys found — run `cadre keys set anthropic`")

    # Check optional tools
    for tool_name in ["git", "dbt", "rg", "sqlfluff", "ruff"]:
        if shutil.which(tool_name):
            console.print(f"  [green]✓[/green] {tool_name}")
        else:
            console.print(f"  [dim]  - {tool_name} (not found, optional)[/dim]")

    console.print()


@main.command(name="config")
@click.argument("action", type=click.Choice(["show"]))
def config_cmd(action: str):
    """Show current configuration."""
    cfg = _load_config()
    if cfg is None:
        return

    console.print("[bold]Current Configuration[/bold]\n")
    console.print(f"  Project:   {cfg.project.name} ({cfg.project.type})")
    console.print(f"  Warehouse: {cfg.project.warehouse}")
    console.print(f"  CI:        {cfg.project.ci_platform}")
    console.print(f"  Mode:      {cfg.team.mode}")
    console.print()
    console.print("  [bold]Agents:[/bold]")
    for name, agent_cfg in cfg.team.agents.items():
        status = "[green]enabled[/green]" if agent_cfg.enabled else "[red]disabled[/red]"
        console.print(f"    {name:12s} {agent_cfg.model:40s} {status}")
        if agent_cfg.extra_context:
            preview = agent_cfg.extra_context[:60].replace("\n", " ")
            console.print(f"    {'':12s} [dim]context: {preview}...[/dim]")
    console.print(f"\n  Workflow:  {cfg.workflows.default}")

    if cfg.context.description:
        console.print("\n  [bold]Project Context:[/bold]")
        console.print(f"    {cfg.context.description}")
    console.print()


def _launch_tui() -> None:
    """Launch the Textual TUI."""
    from cadre.config import CadreConfig
    from cadre.tui.app import CadreTUI

    cfg = _load_config()
    if cfg is None:
        # No config yet — launch TUI with defaults, user can /init inside
        cfg = CadreConfig()

    app = CadreTUI(cfg)
    app.run()


def _show_welcome() -> None:
    """Show the welcome screen with logo and quick status."""
    from cadre.config import CADRE_DIR
    from cadre.ui.logo import print_logo

    print_logo(console, version=__version__)

    cadre_dir = Path.cwd() / CADRE_DIR
    if cadre_dir.exists():
        console.print("  [green]✓[/green] Project configured")
        console.print()
        console.print("  [bold]cadre up[/bold]      Start the AI team")
        console.print("  [bold]cadre chat[/bold]    Chat with your agents")
    else:
        console.print("  [yellow]No project configured yet.[/yellow]")
        console.print()
        console.print("  [bold]cadre init[/bold]    Set up your project")

    console.print()
    console.print("  [dim]Run [bold]cadre --help[/bold] for all commands.[/dim]")
    console.print()


def _load_config() -> CadreConfig | None:
    """Load config from .cadre/ directory, with error handling."""
    from cadre.config import CADRE_DIR, CadreConfig

    base_path = Path.cwd()
    cadre_dir = base_path / CADRE_DIR
    legacy_path = base_path / "cadre.yml"

    if not cadre_dir.exists() and not legacy_path.exists():
        console.print("[red]No configuration found.[/red]")
        console.print("Run [bold]cadre init[/bold] to set up your project.")
        return None

    try:
        return CadreConfig.load(base_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return None
