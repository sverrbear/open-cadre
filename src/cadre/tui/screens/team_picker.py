"""Team picker screen — install a preset team of agents."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from cadre.agents.manager import install_team
from cadre.presets import TEAM_PRESETS, load_preset


class TeamPickerScreen(ModalScreen[bool | None]):
    """Modal for picking and installing a team preset."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    TeamPickerScreen {
        align: center middle;
    }

    #picker-container {
        width: 64;
        height: 30;
        background: #1e1e2e;
        border: thick #313244;
        padding: 1 2;
    }

    #picker-title {
        text-style: bold;
        color: #89b4fa;
        text-align: center;
        margin-bottom: 1;
    }

    #team-list {
        height: 10;
        margin-bottom: 1;
    }

    #preview {
        height: 1fr;
        background: #181825;
        padding: 1;
        margin-bottom: 1;
        border: tall #313244;
    }

    #button-row {
        height: 3;
        align: right middle;
        dock: bottom;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected_team: str = "full"

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-container"):
            yield Label("Install Team Preset", id="picker-title")

            team_options = []
            for name, agents in TEAM_PRESETS.items():
                label = f"{name:12s} ({', '.join(agents)})"
                team_options.append(Option(label, id=name))

            yield OptionList(*team_options, id="team-list")
            yield Static("", id="preview")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Install", variant="primary", id="install-btn")

    def on_mount(self) -> None:
        self._update_preview("full")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self._selected_team = str(event.option.id)
            self._update_preview(self._selected_team)

    def _update_preview(self, team_name: str) -> None:
        agents = TEAM_PRESETS.get(team_name, [])
        lines = [f"[bold]Team: {team_name}[/bold]\n"]
        for name in agents:
            try:
                content = load_preset(name)
                # Extract description from frontmatter
                for line in content.splitlines():
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                        lines.append(f"  [#89b4fa]{name}[/#89b4fa]: {desc[:60]}")
                        break
            except FileNotFoundError:
                lines.append(f"  [#89b4fa]{name}[/#89b4fa]: (preset not found)")

        preview = self.query_one("#preview", Static)
        preview.update("\n".join(lines))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self._selected_team = str(event.option.id)
            self._install()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "install-btn":
            self._install()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _install(self) -> None:
        install_team(self._selected_team)
        self.dismiss(True)
