"""Agent manager — CRUD for .claude/agents/*.md files."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentInfo:
    """Parsed agent definition from a .claude/agents/*.md file."""

    name: str = ""
    description: str = ""
    model: str = ""
    tools: list[str] = field(default_factory=list)
    max_turns: int = 0
    effort: str = ""
    permission_mode: str = ""
    system_prompt: str = ""
    file_path: Path | None = None


CLAUDE_AGENTS_DIR = ".claude/agents"


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body).
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    frontmatter_text = content[3:end].strip()
    body = content[end + 3 :].strip()

    # Simple YAML parsing (key: value per line)
    fm: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\w+)\s*:\s*(.*)$", line)
        if match:
            fm[match.group(1)] = match.group(2).strip()

    return fm, body


def _frontmatter_to_agent(fm: dict[str, str], body: str, file_path: Path) -> AgentInfo:
    """Convert parsed frontmatter + body into an AgentInfo."""
    tools_str = fm.get("tools", "")
    tools = [t.strip() for t in tools_str.split(",") if t.strip()] if tools_str else []

    max_turns = 0
    if fm.get("maxTurns"):
        import contextlib

        with contextlib.suppress(ValueError):
            max_turns = int(fm["maxTurns"])

    return AgentInfo(
        name=fm.get("name", file_path.stem),
        description=fm.get("description", ""),
        model=fm.get("model", ""),
        tools=tools,
        max_turns=max_turns,
        effort=fm.get("effort", ""),
        permission_mode=fm.get("permissionMode", ""),
        system_prompt=body,
        file_path=file_path,
    )


def _agent_to_markdown(agent: AgentInfo) -> str:
    """Convert an AgentInfo back to markdown with frontmatter."""
    lines = ["---"]
    lines.append(f"name: {agent.name}")
    if agent.description:
        lines.append(f"description: {agent.description}")
    if agent.model:
        lines.append(f"model: {agent.model}")
    if agent.tools:
        lines.append(f"tools: {', '.join(agent.tools)}")
    if agent.max_turns:
        lines.append(f"maxTurns: {agent.max_turns}")
    if agent.effort:
        lines.append(f"effort: {agent.effort}")
    if agent.permission_mode:
        lines.append(f"permissionMode: {agent.permission_mode}")
    lines.append("---")
    lines.append("")
    lines.append(agent.system_prompt)
    return "\n".join(lines) + "\n"


def get_agents_dir(project_dir: Path | None = None) -> Path:
    """Get the .claude/agents/ directory path."""
    base = project_dir or Path.cwd()
    return base / CLAUDE_AGENTS_DIR


def list_agents(project_dir: Path | None = None) -> list[AgentInfo]:
    """List all agents from .claude/agents/."""
    agents_dir = get_agents_dir(project_dir)
    if not agents_dir.exists():
        return []

    agents = []
    for path in sorted(agents_dir.glob("*.md")):
        try:
            agent = load_agent(path.stem, project_dir)
            agents.append(agent)
        except Exception:
            continue
    return agents


def load_agent(name: str, project_dir: Path | None = None) -> AgentInfo:
    """Load a single agent by name."""
    agents_dir = get_agents_dir(project_dir)
    path = agents_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent '{name}' not found at {path}")

    content = path.read_text()
    fm, body = _parse_frontmatter(content)
    return _frontmatter_to_agent(fm, body, path)


def save_agent(agent: AgentInfo, project_dir: Path | None = None) -> Path:
    """Save an agent to .claude/agents/<name>.md."""
    agents_dir = get_agents_dir(project_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)

    path = agents_dir / f"{agent.name}.md"
    content = _agent_to_markdown(agent)
    path.write_text(content)
    agent.file_path = path
    return path


def delete_agent(name: str, project_dir: Path | None = None) -> None:
    """Delete an agent's .md file."""
    agents_dir = get_agents_dir(project_dir)
    path = agents_dir / f"{name}.md"
    if path.exists():
        path.unlink()


def install_preset(preset_name: str, project_dir: Path | None = None) -> AgentInfo:
    """Install a single preset agent into .claude/agents/."""
    from cadre.presets import load_preset

    content = load_preset(preset_name)
    agents_dir = get_agents_dir(project_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)

    path = agents_dir / f"{preset_name}.md"
    path.write_text(content)

    fm, body = _parse_frontmatter(content)
    return _frontmatter_to_agent(fm, body, path)


def install_team(team_name: str, project_dir: Path | None = None) -> list[AgentInfo]:
    """Install a full team preset (e.g., 'full' = lead+engineer+architect+qa)."""
    from cadre.presets import TEAM_PRESETS

    agent_names = TEAM_PRESETS.get(team_name, [])
    if not agent_names:
        available = list(TEAM_PRESETS.keys())
        raise ValueError(f"Unknown team preset '{team_name}'. Available: {available}")

    agents = []
    for name in agent_names:
        agent = install_preset(name, project_dir)
        agents.append(agent)
    return agents


def check_claude_cli() -> tuple[bool, str]:
    """Check if claude CLI is available. Returns (available, version_or_error)."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, "claude CLI not found on PATH"

    import subprocess

    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        return True, version
    except Exception as e:
        return False, str(e)


@dataclass
class AuthStatus:
    """Result of checking Claude Code authentication."""

    logged_in: bool = False
    email: str = ""
    org_name: str = ""
    auth_method: str = ""
    error: str = ""


def check_claude_auth() -> AuthStatus:
    """Check if user is authenticated with Claude Code."""
    import json
    import subprocess

    claude_path = shutil.which("claude")
    if not claude_path:
        return AuthStatus(error="Claude Code CLI not found on PATH")

    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return AuthStatus(error=stderr or "Auth check failed")

        data = json.loads(result.stdout)
        return AuthStatus(
            logged_in=data.get("loggedIn", False),
            email=data.get("email", ""),
            org_name=data.get("orgName", ""),
            auth_method=data.get("authMethod", ""),
        )
    except json.JSONDecodeError:
        # Some versions may not support JSON output — try parsing text
        return AuthStatus(error="Could not parse auth status")
    except Exception as e:
        return AuthStatus(error=str(e))
