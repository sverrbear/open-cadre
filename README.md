# OpenCadre

**Open-source, provider-agnostic AI team platform for data engineering.**

Spin up a managed team of AI agents — connect any LLM provider (Anthropic, OpenAI, Google, Mistral, local models via Ollama), configure specialized agents, assign models per role, and manage workflows from your terminal.

## Quick Start

```bash
pip install open-cadre

# See the welcome screen
opencadre

# Interactive setup — detects your project, opens provider dashboards to create API keys
cadre init

# Start your AI team
cadre up
```

## What It Does

- **Provider-agnostic**: Connect 100+ LLM providers via LiteLLM
- **Configurable agents**: Lead, Architect, Engineer, QA — each with their own model, tools, and system prompt
- **Direct agent chat**: `@engineer write a staging model` or let the team lead coordinate
- **Workflow engine**: Out-of-the-box workflows (design → implement → review) + custom YAML workflows
- **Model benchmarks**: See which models perform best per role, compare cost vs quality
- **Terminal-first**: Rich CLI interface, no browser required

## Architecture

```
┌──────────────────────────────────────────────────┐
│                Terminal UI (Rich)                 │
├──────────────────────────────────────────────────┤
│              CLI (Click)                         │
│  cadre init │ up │ chat │ status │ models        │
├──────────────────────────────────────────────────┤
│            Orchestrator Layer                     │
│  Workflow Engine │ Message Router │ Sessions      │
├──────────────────────────────────────────────────┤
│               Agent Layer                        │
│  Lead │ Architect │ Engineer │ QA │ Solo          │
├──────────────────────────────────────────────────┤
│               Tool Layer                         │
│  File Ops │ Shell │ Git │ dbt │ Search           │
├──────────────────────────────────────────────────┤
│         LLM Provider Layer (LiteLLM)             │
│  Anthropic │ OpenAI │ Google │ Mistral │ Ollama  │
└──────────────────────────────────────────────────┘
```

## Commands

Both `cadre` and `opencadre` work as entry points.

| Command | Description |
|---------|-------------|
| `cadre` | Welcome screen with logo and quick status |
| `cadre init` | Interactive setup — detects project, opens provider dashboards for API keys |
| `cadre up` | Start the team and open chat |
| `cadre chat [agent]` | Chat with a specific agent or the team |
| `cadre status` | Show team and agent status |
| `cadre models` | Show model benchmarks and recommendations |
| `cadre workflow list` | List available workflows |
| `cadre workflow run <name> <request>` | Run a workflow |
| `cadre doctor` | Check prerequisites and configuration |
| `cadre config show` | Show current configuration |

### Slash Commands (in chat)

Once inside `cadre chat` or `cadre up`, use slash commands:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/status` | Show team and agent status |
| `/explore` | Explore codebase and update agent context |
| `/models` | Show model benchmarks and recommendations |
| `/doctor` | Check prerequisites and configuration |
| `/config` | Show current configuration |
| `/workflow list` | List available workflows |
| `/workflow run <name> <request>` | Run a workflow |
| `/quit` | Exit the chat |

## Configuration

All configuration lives in `.cadre/config.yml` (created by `cadre init`). See [`cadre.example.yml`](cadre.example.yml) for a full example.

```yaml
project:
  name: "My Analytics Project"
  type: dbt
  warehouse: snowflake

providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
  openai:
    api_key: ${OPENAI_API_KEY}

team:
  mode: full    # full (4 agents) or solo (1 agent)
  agents:
    lead:
      model: anthropic/claude-opus-4-6
    architect:
      model: anthropic/claude-sonnet-4-6
    engineer:
      model: openai/gpt-4o          # Mix providers!
    qa:
      model: anthropic/claude-sonnet-4-6
```

## Agents

| Agent | Role | Can Write Code |
|-------|------|:-:|
| **Lead** | Coordinates team, routes tasks | No |
| **Architect** | Designs models, classifies risk | No |
| **Engineer** | Implements designs, writes SQL/dbt | Yes |
| **QA** | Reviews implementations | No |
| **Solo** | All-in-one (solo mode) | Yes |

## Workflows

Built-in workflows:

- **design-implement-review** — Architect designs → Engineer implements → QA reviews
- **code-review** — QA reviews current changes
- **model-creation** — Full pipeline with staging layer check

Define custom workflows in `cadre.yml`:

```yaml
workflows:
  quick-fix:
    description: "Quick fix without full review"
    steps:
      - agent: engineer
        instruction: "Fix this issue"
      - agent: qa
        instruction: "Quick review"
        wait_for_approval: true
```

## Development

```bash
git clone https://github.com/your-org/open-cadre.git
cd open-cadre
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0
