"""Header bar widget — project name, version, and keybind hints."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Label


class HeaderBar(Widget):
    """Top bar showing project info and keyboard shortcuts."""

    DEFAULT_CSS = """
    HeaderBar {
        layout: horizontal;
        height: 3;
        align: left middle;
    }

    HeaderBar #keybinds {
        dock: right;
        width: auto;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        project_name: str = "OpenCadre",
        version: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.project_name = project_name
        self.version = version

    def compose(self) -> ComposeResult:
        with Horizontal():
            version_str = f" v{self.version}" if self.version else ""
            yield Label(
                f" [bold]OpenCadre[/bold]{version_str} — {self.project_name}",
                id="title",
            )
            yield Label(
                "N new | I install team | L launch claude | D delete | ctrl+q quit ",
                id="keybinds",
            )
