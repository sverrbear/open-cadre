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
pytest tests/test_agents.py::test_agent_creation -v

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

OpenCadre is a provider-agnostic AI team platform for data engineering. Users configure teams of specialized AI agents that collaborate via a terminal UI.

**Layered architecture (bottom-up):**

1. **Providers** (`src/cadre/providers/`) — LiteLLM-based unified interface to 100+ LLM providers. `LiteLLMProvider` handles async streaming. `ProviderRegistry` manages API keys.

2. **Tools** (`src/cadre/tools/`) — `Tool` base class produces OpenAI-format schemas. Implementations: file_ops, git, dbt, shell, search. `ToolRegistry` for central registration. Shell tools use `shell_allow`/`shell_deny` permission patterns from config.

3. **Agents** (`src/cadre/agents/`) — `Agent` holds role, model, tools, history. `AgentLoop` runs the tool-calling loop (max 25 iterations). Five presets via `PRESET_FACTORIES`: Team Lead, Architect, Engineer, QA, Solo.

4. **Orchestration** (`src/cadre/orchestrator/`) — `Team` manages agent lifecycle. `MessageRouter` parses @mentions and dispatches to agents. `Session` tracks conversation state.

5. **Workflows** (`src/cadre/workflows/`) — `WorkflowEngine` executes multi-step `WorkflowDef`s, accumulating context between steps. Steps can have conditions and approval gates. Three presets: design-implement-review, code-review, model-creation.

6. **UI** (`src/cadre/ui/`) — Rich-based terminal app. `ChatUI` for interactive chat, `StatusUI` for team status display.

7. **CLI** (`src/cadre/cli.py`) — Click-based. Entry point: `cadre = cadre.cli:main`. Commands: init, explore, up, chat, status, models, workflow, doctor, config.

**Configuration system:** Lives in `.cadre/` directory — `config.yml` (main), `agents/<name>.yml` (per-agent), `context.yml` (auto-populated project context). Supports `${ENV_VAR}` substitution. Legacy `cadre.yml` also supported.

**Event system:** `AgentEvent` types (content_delta, tool_call, response, error, status) flow from AgentLoop through Router/WorkflowEngine to the UI layer.

## Code Conventions

- Python 3.10+ (tested on 3.10–3.13)
- Line length: 100 characters
- Ruff rules: E, F, I, N, W, UP, B, SIM, RUF
- Tests use `asyncio_mode = "auto"` — async tests are detected automatically
- Shared test fixtures (`sample_config`, `solo_config`) in `tests/conftest.py`
- Templates use Jinja2 (`src/cadre/templates/`)
