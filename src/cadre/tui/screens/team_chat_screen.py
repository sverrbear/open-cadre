"""Team chat screen — unified multi-agent chat interface."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Label, RichLog, Select

from cadre.agents.router import TeamMessage, TeamRouter
from cadre.tui.screens.chat_screen import ChatInput
from cadre.tui.screens.chat_settings import ChatSessionSettings
from cadre.tui.widgets.team_agent_card import TeamAgentCard, agent_color

if TYPE_CHECKING:
    from cadre.agents.manager import AgentInfo


class TeamChatScreen(Screen):
    """Unified team chat with all agents visible."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "go_back", "Back", show=True),
    ]

    DEFAULT_CSS = """
    TeamChatScreen {
        layout: vertical;
    }

    #team-header {
        height: 3;
        background: #313244;
        padding: 0 2;
        layout: horizontal;
        align: left middle;
    }

    #team-header #team-back-btn {
        min-width: 8;
        margin-right: 2;
    }

    #team-header #team-title {
        width: 1fr;
        color: #89b4fa;
        text-style: bold;
    }

    #team-body {
        height: 1fr;
        layout: horizontal;
    }

    #team-log {
        width: 1fr;
        background: #1e1e2e;
        padding: 0 2;
        scrollbar-size: 1 1;
    }

    #team-sidebar {
        width: 30;
        background: #181825;
        padding: 1;
        border-left: solid #313244;
    }

    #team-sidebar-title {
        color: #6c7086;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    .team-agent-card {
        height: auto;
        min-height: 2;
        padding: 0;
        margin-bottom: 1;
    }

    #team-status-bar {
        height: 1;
        background: #313244;
        padding: 0 2;
        color: #6c7086;
    }

    #team-input-bar {
        height: auto;
        min-height: 3;
        max-height: 8;
        background: #313244;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
    }

    #team-agent-select {
        width: 16;
        height: auto;
        min-height: 1;
    }

    #team-input {
        width: 1fr;
        height: auto;
        min-height: 1;
        max-height: 5;
        background: #45475a;
        color: #cdd6f4;
        border: none;
        margin-left: 1;
    }

    #team-input:focus {
        border: none;
    }

    #team-send-btn {
        min-width: 8;
        margin-left: 1;
    }

    #team-stop-btn {
        min-width: 8;
        margin-left: 1;
        display: none;
    }
    """

    class GoBack(Message):
        pass

    def __init__(
        self,
        team_name: str,
        agents: list[AgentInfo],
        settings: ChatSessionSettings | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._team_name = team_name
        self._agents = agents
        self._settings = settings or ChatSessionSettings()
        self._agent_cards: dict[str, TeamAgentCard] = {}
        self._is_streaming = False

        # Text buffers per agent (accumulate until result event)
        self._agent_text_buffers: dict[str, str] = {}
        self._agent_header_shown: dict[str, bool] = {}
        self._active_agents: set[str] = set()

        # Router
        self._router = TeamRouter()
        self._router.on_message = self._on_team_message
        self._router.on_agent_status_change = self._on_agent_status
        self._router.on_permission_needed = self._on_permission_needed

    def compose(self) -> ComposeResult:
        agent_names = [a.name for a in self._agents]
        default_target = "lead" if "lead" in agent_names else agent_names[0]

        with Vertical():
            with Horizontal(id="team-header"):
                yield Button("\u2190 Back", variant="default", id="team-back-btn")
                yield Label(f"Team Chat: {self._team_name}", id="team-title")

            with Horizontal(id="team-body"):
                yield RichLog(
                    highlight=True,
                    markup=True,
                    wrap=True,
                    auto_scroll=True,
                    id="team-log",
                )
                with Vertical(id="team-sidebar"):
                    yield Label("TEAM", id="team-sidebar-title")
                    for agent in self._agents:
                        card = TeamAgentCard(
                            agent_name=agent.name,
                            classes="team-agent-card",
                            id=f"team-card-{agent.name}",
                        )
                        self._agent_cards[agent.name] = card
                        yield card

            yield Label("", id="team-status-bar")

            with Horizontal(id="team-input-bar"):
                options = [(f"@{name}", name) for name in agent_names]
                yield Select(
                    options,
                    value=default_target,
                    id="team-agent-select",
                )
                yield ChatInput(id="team-input")
                yield Button("Send", variant="primary", id="team-send-btn")
                yield Button("Stop", variant="error", id="team-stop-btn")

    def on_mount(self) -> None:
        # Start the team router
        self._router.start_team(self._team_name, self._agents, self._settings)

        log = self.query_one("#team-log", RichLog)
        agent_list = ", ".join(
            f"[bold {agent_color(a.name)}]@{a.name}[/bold {agent_color(a.name)}]"
            for a in self._agents
        )
        log.write(
            f"[dim]Team chat started with {agent_list}. Messages go to the selected agent.[/dim]\n"
        )

        text_area = self.query_one("#team-input", ChatInput)
        text_area.show_line_numbers = False
        text_area.tab_behavior = "focus"
        text_area.focus()

    # ── TeamRouter callbacks ────────────────────────────────────────────

    def _on_team_message(self, msg: TeamMessage) -> None:
        """Render a TeamMessage in the unified timeline."""
        log = self.query_one("#team-log", RichLog)

        if msg.message_type == "user":
            color = agent_color(msg.recipient)
            log.write(
                f"\n[bold #cdd6f4]You[/bold #cdd6f4] "
                f"[dim]\u2192 @{msg.recipient}:[/dim] "
                f"{msg.content}"
            )

        elif msg.message_type == "agent_text":
            se = msg.stream_event
            if not se:
                return

            name = msg.sender
            color = agent_color(name)

            if se.event_type in ("assistant", "content_block_delta"):
                if se.text:
                    # Buffer text per agent
                    buf = self._agent_text_buffers.get(name, "")
                    self._agent_text_buffers[name] = buf + se.text

                    # Show header on first text
                    if not self._agent_header_shown.get(name, False):
                        log.write(f"\n[bold {color}][{name}][/bold {color}]")
                        self._agent_header_shown[name] = True

            elif se.event_type == "result":
                # Flush the buffer
                buffered = self._agent_text_buffers.pop(name, "")
                if buffered:
                    log.write(f"[{color}]{buffered}[/{color}]")
                elif se.result_text:
                    if not self._agent_header_shown.get(name, False):
                        log.write(f"\n[bold {color}][{name}][/bold {color}]")
                    log.write(f"[{color}]{se.result_text}[/{color}]")

                self._agent_header_shown[name] = False

                # Update token display
                session = self._router.get_session(name)
                if session:
                    total_in = sum(s.total_input_tokens for s in self._router.sessions.values())
                    total_out = sum(s.total_output_tokens for s in self._router.sessions.values())
                    parts = []
                    if total_in:
                        parts.append(f"in:{total_in:,}")
                    if total_out:
                        parts.append(f"out:{total_out:,}")
                    if parts:
                        log.write(f"[dim #585b70]  tokens: {' '.join(parts)}[/dim #585b70]")
                log.write("")  # blank separator

                # Check if any agents still active
                self._active_agents.discard(name)
                if not self._active_agents:
                    self._set_streaming(False)

        elif msg.message_type == "agent_tool":
            # Show ephemerally in the agent's sidebar card
            card = self._agent_cards.get(msg.sender)
            if card:
                card.current_task = msg.content

        elif msg.message_type == "routing":
            log.write(f"[dim]  [{msg.sender} \u2192 {msg.recipient}] {msg.content}[/dim]")

        elif msg.message_type == "system":
            log.write(f"[dim #6c7086][system] {msg.content}[/dim #6c7086]")

        elif msg.message_type == "error":
            log.write(f"[bold red][{msg.sender}] Error:[/bold red] {msg.content}")

    def _on_agent_status(self, agent_name: str, status: str, task: str) -> None:
        """Update the sidebar card for this agent."""
        card = self._agent_cards.get(agent_name)
        if card:
            card.status = status
            card.current_task = task

        # Update status bar
        active = [n for n, s in self._router.sessions.items() if s.status != "idle"]
        status_bar = self.query_one("#team-status-bar", Label)
        if active:
            status_bar.update(f"[dim]Active: {', '.join(active)}[/dim]")
        else:
            status_bar.update("")

    async def _on_permission_needed(self, agent_name: str, event: dict) -> bool:
        """Show permission dialog for an agent."""
        from cadre.tui.screens.permission_dialog import PermissionDialog

        request = event.get("request", {})
        tool_name = request.get("tool_name", "unknown")
        tool_input = request.get("input", {})
        reason = request.get("decision_reason", "")

        log = self.query_one("#team-log", RichLog)
        if isinstance(tool_input, dict) and tool_name == "Bash":
            cmd = tool_input.get("command", "")
            log.write(
                f"[dim #f9e2af]  [{agent_name}] "
                f"\u26a0 Permission: {tool_name} \u2014 {cmd}"
                f"[/dim #f9e2af]"
            )
        else:
            log.write(f"[dim #f9e2af]  [{agent_name}] \u26a0 Permission: {tool_name}[/dim #f9e2af]")

        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()

        def on_result(allowed: bool | None) -> None:
            if not future.done():
                future.set_result(bool(allowed))

        self.app.push_screen(
            PermissionDialog(
                tool_name=tool_name,
                tool_input=tool_input,
                reason=reason,
                agent_name=agent_name,
            ),
            callback=on_result,
        )

        allowed = await future

        if allowed:
            status = "[bold green]\u2713 Allowed[/bold green]"
        else:
            status = "[bold red]\u2717 Denied[/bold red]"
        log.write(f"[dim]  {status}[/dim]")

        return allowed

    # ── Input handling ──────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "team-back-btn":
            self.action_go_back()
        elif event.button.id == "team-send-btn":
            self._submit_input()
        elif event.button.id == "team-stop-btn":
            self._router.stop_all()
            self._set_streaming(False)

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle Enter in team chat input."""
        self._submit_input()

    def _submit_input(self) -> None:
        text_area = self.query_one("#team-input", ChatInput)
        message = text_area.text.strip()
        if not message or self._is_streaming:
            return

        text_area.clear()

        # Get target agent from selector
        select = self.query_one("#team-agent-select", Select)
        target = select.value if isinstance(select.value, str) else "lead"

        # Check for @mention override in the message text
        if message.startswith("@"):
            for name in self._router.agent_names:
                prefix = f"@{name}"
                if message.startswith(prefix) and (
                    len(message) == len(prefix) or message[len(prefix)] in (" ", "\n", "\t")
                ):
                    target = name
                    # Update selector to match
                    select.value = name
                    break

        self._active_agents.add(target)
        self._set_streaming(True)
        self._do_send(message, target)

    @work(thread=False)
    async def _do_send(self, message: str, target: str) -> None:
        """Send message via TeamRouter."""
        await self._router.send_user_message(message, target=target)

    def _set_streaming(self, streaming: bool) -> None:
        self._is_streaming = streaming
        text_area = self.query_one("#team-input", ChatInput)
        send_btn = self.query_one("#team-send-btn", Button)
        stop_btn = self.query_one("#team-stop-btn", Button)

        text_area.disabled = streaming
        send_btn.display = not streaming
        stop_btn.display = streaming

        if not streaming:
            text_area.focus()

    def action_go_back(self) -> None:
        self._router.stop_all()
        self.post_message(self.GoBack())
