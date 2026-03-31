"""Agent editor screen — create or edit a .claude/agents/*.md file."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, TextArea

from cadre.agents.manager import AgentInfo, delete_agent, save_agent

MODELS = [
    ("Default (inherit)", ""),
    ("Opus", "opus"),
    ("Sonnet", "sonnet"),
    ("Haiku", "haiku"),
]

TOOL_OPTIONS = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "Agent",
    "WebSearch",
    "WebFetch",
    "NotebookEdit",
]

EFFORT_OPTIONS = [
    ("Default", ""),
    ("Low", "low"),
    ("Medium", "medium"),
    ("High", "high"),
    ("Max", "max"),
]


class AgentEditorScreen(ModalScreen[bool | None]):
    """Modal for creating/editing an agent."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AgentEditorScreen {
        align: center middle;
    }

    #editor-container {
        width: 76;
        height: 42;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #editor-title {
        text-style: bold;
        color: #89b4fa;
        text-align: center;
        margin-bottom: 1;
    }

    .field-label {
        color: #6c7086;
        margin-top: 1;
    }

    Input {
        margin-bottom: 0;
    }

    Select {
        margin-bottom: 0;
    }

    #prompt-editor {
        height: 12;
        margin-bottom: 1;
    }

    #tools-input {
        margin-bottom: 0;
    }

    .field-hint {
        color: #585b70;
        margin-bottom: 1;
    }

    #button-row {
        height: 3;
        align: right middle;
        margin-top: 1;
        dock: bottom;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, agent: AgentInfo | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.is_new = agent is None

    def compose(self) -> ComposeResult:
        agent = self.agent or AgentInfo()
        title = "New Agent" if self.is_new else f"Edit: {agent.name}"

        with Vertical(id="editor-container"):
            yield Label(title, id="editor-title")

            yield Label("Name", classes="field-label")
            yield Input(
                value=agent.name,
                placeholder="e.g., engineer",
                id="agent-name",
                disabled=not self.is_new,
            )

            yield Label("Description", classes="field-label")
            yield Input(
                value=agent.description,
                placeholder="What this agent does (used by Claude to decide when to delegate)",
                id="agent-desc",
            )

            with Horizontal():
                with Vertical():
                    yield Label("Model", classes="field-label")
                    yield Select(
                        MODELS,
                        value=agent.model,
                        id="agent-model",
                        allow_blank=False,
                    )
                with Vertical():
                    yield Label("Effort", classes="field-label")
                    yield Select(
                        EFFORT_OPTIONS,
                        value=agent.effort,
                        id="agent-effort",
                        allow_blank=False,
                    )

            yield Label("Tools (comma-separated)", classes="field-label")
            yield Input(
                value=", ".join(agent.tools),
                placeholder="Read, Write, Edit, Bash, Glob, Grep, Agent",
                id="tools-input",
            )
            yield Label(
                f"[dim]Available: {', '.join(TOOL_OPTIONS)}[/dim]",
                classes="field-hint",
            )

            yield Label("System Prompt", classes="field-label")
            yield TextArea(
                text=agent.system_prompt,
                id="prompt-editor",
            )

            with Horizontal(id="button-row"):
                if not self.is_new:
                    yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Save", variant="primary", id="save-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "save-btn":
            self._save()
        elif event.button.id == "delete-btn":
            self._confirm_delete()

    def _confirm_delete(self) -> None:
        from cadre.tui.screens.confirm_dialog import ConfirmDialog

        self.app.push_screen(
            ConfirmDialog(
                title="Delete Agent",
                message=f"Delete agent '{self.agent.name}'? This cannot be undone.",
            ),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, result: bool | None) -> None:
        if result and self.agent:
            delete_agent(self.agent.name)
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save(self) -> None:
        name = self.query_one("#agent-name", Input).value.strip()
        if not name:
            return

        description = self.query_one("#agent-desc", Input).value.strip()
        model = str(self.query_one("#agent-model", Select).value)
        effort = str(self.query_one("#agent-effort", Select).value)
        tools_str = self.query_one("#tools-input", Input).value
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        system_prompt = self.query_one("#prompt-editor", TextArea).text

        agent = AgentInfo(
            name=name,
            description=description,
            model=model,
            tools=tools,
            effort=effort,
            system_prompt=system_prompt,
        )

        save_agent(agent)
        self.dismiss(True)
