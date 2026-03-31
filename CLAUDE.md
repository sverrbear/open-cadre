# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install for development (includes pytest, pytest-asyncio, ruff)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_agents.py

# Run a single test
pytest tests/test_agents.py::test_parse_frontmatter -v

# Lint
ruff check src/ tests/

# Format check
ruff format --check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Auto-format
ruff format src/ tests/
```

## Architecture

OpenCadre is a **Claude Code team management frontend**. It provides a TUI for creating, editing, and managing Claude Code agent teams via `.claude/agents/*.md` files, then launching Claude Code with those agents active.

**Layers:**

1. **Agent Manager** (`src/cadre/agents/manager.py`) — CRUD for `.claude/agents/*.md` files. Parses/generates markdown with YAML frontmatter (name, description, model, tools, maxTurns, effort, permissionMode). Key types: `AgentInfo` dataclass, functions: `list_agents`, `load_agent`, `save_agent`, `delete_agent`, `install_preset`, `install_team`, `check_claude_cli`.

2. **Presets** (`src/cadre/presets/`) — Ready-made agent templates as `.md` files: lead, engineer, architect, qa, solo. Team presets in `TEAM_PRESETS`: full (4 agents), solo, dev, review. Functions: `list_presets`, `load_preset`, `list_team_presets`.

3. **TUI** (`src/cadre/tui/`) — Textual-based terminal UI.
   - `app.py` — Main `CadreTUI` app. Launches main screen, handles Claude Code launch (suspends TUI, runs `claude` subprocess), agent refresh.
   - `screens/main_screen.py` — Agent dashboard with cards, action buttons (Launch Claude, New Agent, Install Team).
   - `screens/agent_editor.py` — Modal form for creating/editing agents (name, description, model, tools, effort, system prompt).
   - `screens/team_picker.py` — Modal for selecting and installing team presets.
   - `screens/settings_screen.py` — Theme and UI settings.
   - `widgets/header_bar.py` — Top bar with keybind hints.
   - `widgets/status_sidebar.py` — Sidebar showing installed agents.
   - `themes/` — TCSS theme files (dark, light, monokai).

4. **CLI** (`src/cadre/cli.py`) — Click-based. Entry points: `cadre` and `opencadre`.
   - `opencadre` (no args) — Launch TUI
   - `opencadre init [preset]` — Install team preset (full/solo/dev/review)
   - `opencadre agents` — List installed agents
   - `opencadre chat [agent]` — Launch Claude Code directly
   - `opencadre doctor` — Check prerequisites (Python, claude CLI, agents)
   - `opencadre up` — Launch TUI

5. **Config** (`src/cadre/config.py`) — Minimal Pydantic config: `ProjectConfig` (name), `TeamConfig` (mode, preset), `UIConfig` (theme, sidebar_visible). Saved to `.cadre/config.yml`.

**Key concept:** Agents are native Claude Code `.claude/agents/*.md` files with YAML frontmatter. OpenCadre manages these files — it does NOT implement its own LLM provider, tools, or agent execution. Claude Code handles all of that natively.

## Code Conventions

- Python 3.10+ (tested on 3.10–3.13)
- Line length: 100 characters
- Ruff rules: E, F, I, N, W, UP, B, SIM, RUF
- Tests use `asyncio_mode = "auto"` — async tests are detected automatically
- Shared test fixtures in `tests/conftest.py`

## Workflow Reminders

- When making changes that affect CLI commands, configuration, or user-facing features, check whether `README.md` needs to be updated
- Always create new branches from `main` (checkout main first, then create the branch)
