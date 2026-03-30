"""Codebase exploration — `cadre explore` uses an LLM to analyze your project."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.status import Status

from cadre.config import CADRE_DIR, CadreConfig, ProjectContext

console = Console()

# Files to skip when scanning
SKIP_DIRS = {
    ".git",
    ".cadre",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".eggs",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
}

# Key files to read in full for context
KEY_FILES = [
    "README.md",
    "README.rst",
    "README.txt",
    "dbt_project.yml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Makefile",
    "docker-compose.yml",
    "Dockerfile",
    ".github/workflows/ci.yml",
    "schema.yml",
]

# File extensions to count
CODE_EXTENSIONS = {
    ".sql",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".md",
    ".txt",
    ".sh",
    ".js",
    ".ts",
}

EXPLORE_PROMPT = """\
You are analyzing a software project to help configure AI agents that will work on it.

Here is what we know about the project:
- Name: {project_name}
- Type: {project_type}
- Warehouse: {warehouse}

Here is the directory tree:
```
{tree}
```

Here are the key files we found:
{key_file_contents}

File counts by extension:
{file_counts}

Based on this analysis, provide a JSON response with these fields:
{{
    "description": "A 1-2 sentence description of what this project does",
    "tech_stack": ["list", "of", "technologies", "and", "versions"],
    "conventions": [
        "coding conventions you can infer from the codebase",
        "e.g. naming patterns, architecture patterns, testing patterns"
    ],
    "key_paths": {{
        "models": "path/to/models if applicable",
        "tests": "path/to/tests",
        "other_key_dir": "path"
    }},
    "notes": "any important observations about the project structure or patterns",
    "agent_context": {{
        "lead": "specific context the team lead agent should know about this project",
        "architect": "specific context the architect agent should know",
        "engineer": "specific context the engineer agent should know",
        "qa": "specific context the QA agent should know",
        "solo": "specific context the solo agent should know"
    }}
}}

Respond with ONLY valid JSON, no markdown fences or other text."""


def run_explore(base_path: Path | None = None, model: str | None = None) -> None:
    """Explore the codebase and populate .cadre/ with project context."""
    if base_path is None:
        base_path = Path.cwd()

    cadre_dir = base_path / CADRE_DIR
    if not cadre_dir.exists():
        console.print("[red].cadre/ not found.[/red] Run [bold]cadre init[/bold] first.")
        raise SystemExit(1)

    config = CadreConfig.load(base_path)

    if not config.providers:
        console.print("[red]No API keys configured.[/red] Run [bold]cadre init[/bold] first.")
        raise SystemExit(1)

    # Pick a model for exploration
    explore_model = model or _pick_model(config)
    console.print(f"  Using [cyan]{explore_model}[/cyan] for analysis\n")

    # Scan the codebase
    console.print("  Scanning codebase...")
    tree = _build_tree(base_path)
    key_contents = _read_key_files(base_path)
    file_counts = _count_files(base_path)

    total_files = sum(file_counts.values())
    console.print(f"  Found {total_files} files across {len(file_counts)} types\n")

    # Build the prompt
    key_file_text = ""
    for fpath, content in key_contents.items():
        key_file_text += f"\n--- {fpath} ---\n{content}\n"

    counts_text = "\n".join(f"  {ext}: {count}" for ext, count in sorted(file_counts.items()))

    prompt = EXPLORE_PROMPT.format(
        project_name=config.project.name,
        project_type=config.project.type,
        warehouse=config.project.warehouse,
        tree=tree,
        key_file_contents=key_file_text or "(no key files found)",
        file_counts=counts_text or "(no code files found)",
    )

    # Call the LLM
    with Status("  Analyzing with LLM...", console=console, spinner="dots"):
        result = asyncio.run(_call_llm(config, explore_model, prompt))

    if result is None:
        console.print("[red]  Failed to get a response from the LLM.[/red]")
        raise SystemExit(1)

    # Parse the result
    analysis = _parse_response(result)
    if analysis is None:
        console.print("[red]  Failed to parse LLM response.[/red]")
        console.print(f"  [dim]Raw response: {result[:500]}[/dim]")
        raise SystemExit(1)

    # Update context.yml
    context = ProjectContext(
        description=analysis.get("description", ""),
        tech_stack=analysis.get("tech_stack", []),
        conventions=analysis.get("conventions", []),
        key_paths=analysis.get("key_paths", {}),
        notes=analysis.get("notes", ""),
    )
    config.context = context

    # Update agent extra_context
    agent_contexts = analysis.get("agent_context", {})
    for agent_name, extra in agent_contexts.items():
        if agent_name in config.team.agents:
            config.team.agents[agent_name].extra_context = extra
        elif extra:
            # Agent not in config yet (e.g. solo when in full mode) — skip
            pass

    # Save everything
    config.save(base_path)

    # Print results
    console.print(f"\n  [green]✓[/green] {analysis.get('description', 'Analysis complete')}")
    if analysis.get("tech_stack"):
        console.print(f"  [green]✓[/green] Tech stack: {', '.join(analysis['tech_stack'][:6])}")
    if analysis.get("conventions"):
        console.print(f"  [green]✓[/green] Found {len(analysis['conventions'])} conventions")
    updated_agents = [n for n in agent_contexts if n in config.team.agents and agent_contexts[n]]
    if updated_agents:
        console.print(f"  [green]✓[/green] Updated agent context: {', '.join(updated_agents)}")

    console.print(f"\n  Updated {CADRE_DIR}/context.yml")
    for name in updated_agents:
        console.print(f"  Updated {CADRE_DIR}/agents/{name}.yml")
    console.print("\n  Your agents are now configured for this project.\n")


def _pick_model(config: CadreConfig) -> str:
    """Pick the best available model for exploration."""
    # Prefer a fast, capable model
    preferences = [
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-haiku-4-5-20251001",
        "openai/gpt-4o",
        "anthropic/claude-opus-4-6",
    ]

    available_providers = set(config.providers.keys())
    for model in preferences:
        provider = model.split("/")[0]
        if provider in available_providers:
            return model

    # Fall back to first configured agent's model
    for agent_cfg in config.team.agents.values():
        return agent_cfg.model

    return "anthropic/claude-sonnet-4-6"


async def _call_llm(config: CadreConfig, model: str, prompt: str) -> str | None:
    """Call the LLM and return the text response."""
    from cadre.providers.litellm_provider import LiteLLMProvider
    from cadre.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    for name, pcfg in config.providers.items():
        registry.add_provider(name, api_key=pcfg.api_key, api_base=pcfg.api_base)

    provider = LiteLLMProvider(
        api_keys=registry.get_api_keys(),
        api_bases=registry.get_api_bases(),
    )

    messages = [{"role": "user", "content": prompt}]

    try:
        response_text = ""
        async for chunk in provider.complete(messages, model=model, stream=False):
            if chunk.get("type") == "message_complete":
                response_text = chunk["message"].get("content", "")
        return response_text
    except Exception as e:
        console.print(f"  [red]LLM error: {e}[/red]")
        return None


def _parse_response(text: str) -> dict[str, Any] | None:
    """Parse the LLM's JSON response."""
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first and last fence lines
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
        return None


def _build_tree(base_path: Path, max_depth: int = 3) -> str:
    """Build a directory tree string."""
    lines: list[str] = []

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return

        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        dirs = [e for e in entries if e.is_dir() and e.name not in SKIP_DIRS]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".")]

        # Show files at this level (limit to 15)
        for f in files[:15]:
            lines.append(f"{prefix}{f.name}")
        if len(files) > 15:
            lines.append(f"{prefix}... ({len(files) - 15} more files)")

        # Recurse into directories
        for d in dirs:
            lines.append(f"{prefix}{d.name}/")
            _walk(d, prefix + "  ", depth + 1)

    _walk(base_path, "", 0)
    return "\n".join(lines[:200])  # Cap at 200 lines


def _read_key_files(base_path: Path) -> dict[str, str]:
    """Read key project files for context."""
    contents: dict[str, str] = {}
    for rel_path in KEY_FILES:
        full_path = base_path / rel_path
        if full_path.exists() and full_path.is_file():
            try:
                text = full_path.read_text(encoding="utf-8", errors="replace")
                # Truncate large files
                if len(text) > 3000:
                    text = text[:3000] + "\n... (truncated)"
                contents[rel_path] = text
            except Exception:
                pass

    # Also look for schema.yml files in common dbt locations
    for schema_path in base_path.glob("models/**/schema.yml"):
        rel = str(schema_path.relative_to(base_path))
        try:
            text = schema_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 2000:
                text = text[:2000] + "\n... (truncated)"
            contents[rel] = text
        except Exception:
            pass

    return contents


def _count_files(base_path: Path) -> dict[str, int]:
    """Count files by extension."""
    counts: dict[str, int] = {}
    for path in base_path.rglob("*"):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.is_file() and path.suffix in CODE_EXTENSIONS:
            counts[path.suffix] = counts.get(path.suffix, 0) + 1
    return counts
