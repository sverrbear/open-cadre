"""Main screen — primary multi-pane layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen

from cadre.tui.widgets.agent_tabs import AgentTabs
from cadre.tui.widgets.header_bar import HeaderBar
from cadre.tui.widgets.input_bar import InputBar
from cadre.tui.widgets.status_sidebar import StatusSidebar
from cadre.tui.widgets.tool_output import ToolOutputPanel

if TYPE_CHECKING:
    from cadre.config import CadreConfig
    from cadre.orchestrator.team import Team


class MainScreen(Screen):
    """Primary screen with chat, status sidebar, and tool output."""

    def __init__(
        self,
        config: CadreConfig,
        team: Team,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.team = team

    def compose(self) -> ComposeResult:
        from cadre import __version__

        # Gather agent info for widgets
        agent_names = list(self.team.agents.keys())
        agent_info = {}
        for name, agent in self.team.agents.items():
            agent_info[name] = {
                "role": agent.role,
                "model": agent.model,
            }

        project_name = self.config.project.name
        warehouse = self.config.project.warehouse
        subtitle = f"{project_name}"
        if warehouse:
            subtitle += f" ({warehouse})"

        yield HeaderBar(project_name=subtitle, version=__version__)

        with Horizontal(id="main-content"):
            with Vertical(id="chat-area"):
                yield AgentTabs(agent_names=agent_names)
                yield ToolOutputPanel()
            yield StatusSidebar(agents=agent_info)

        yield InputBar(agent_names=agent_names)

    def on_mount(self) -> None:
        """Focus the input bar when the screen mounts."""
        self.query_one(InputBar).focus_input()
