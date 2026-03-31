"""Team management tool — enables the team lead to add/remove agents dynamically."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadre.tools.base import Tool

if TYPE_CHECKING:
    from cadre.orchestrator.team import Team


class TeamManagementTool(Tool):
    """Manage the agent team — add/remove agents, list team, update context."""

    def __init__(self) -> None:
        self._team: Team | None = None
        super().__init__(
            name="manage_team",
            description=(
                "Manage your agent team. Add or remove specialist agents, "
                "view current team composition, or update agent context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list_presets",
                            "list_team",
                            "add_agent",
                            "remove_agent",
                            "update_context",
                        ],
                        "description": "The team management action to perform",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": (
                            "Name of the agent preset (for add_agent) "
                            "or agent (for remove_agent/update_context)"
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "Extra context to provide the agent about the project "
                            "(for add_agent or update_context)"
                        ),
                    },
                },
                "required": ["action"],
            },
        )

    def set_team(self, team: Team) -> None:
        """Inject the team reference (called after team construction)."""
        self._team = team

    async def execute(self, args: dict[str, Any]) -> str:
        """Execute a team management action."""
        if self._team is None:
            return "Error: team management not available (team not initialized)"

        action = args.get("action", "")
        agent_name = args.get("agent_name", "")
        context = args.get("context", "")

        if action == "list_presets":
            return self._list_presets()
        elif action == "list_team":
            return self._list_team()
        elif action == "add_agent":
            return self._add_agent(agent_name, context)
        elif action == "remove_agent":
            return self._remove_agent(agent_name)
        elif action == "update_context":
            return self._update_context(agent_name, context)
        else:
            return f"Error: unknown action '{action}'"

    def _list_presets(self) -> str:
        from cadre.agents.presets import PRESET_DESCRIPTIONS

        lines = ["Available specialist agents:\n"]
        current_team = set(self._team.agents.keys())
        for name, desc in PRESET_DESCRIPTIONS.items():
            status = " (already on team)" if name in current_team else ""
            lines.append(f"  - {name}: {desc}{status}")
        return "\n".join(lines)

    def _list_team(self) -> str:
        if not self._team.agents:
            return "No agents on the team."
        lines = ["Current team:\n"]
        for name, agent in self._team.agents.items():
            lines.append(f"  - {name}: {agent.role} [model: {agent.model}]")
        return "\n".join(lines)

    def _add_agent(self, agent_name: str, context: str) -> str:
        if not agent_name:
            return "Error: agent_name is required for add_agent"

        from cadre.agents.presets import PRESET_DESCRIPTIONS

        if agent_name not in PRESET_DESCRIPTIONS:
            available = ", ".join(PRESET_DESCRIPTIONS.keys())
            return f"Error: '{agent_name}' is not a valid specialist preset. Available: {available}"

        if agent_name in self._team.agents:
            return f"'{agent_name}' is already on the team."

        agent = self._team.add_agent(agent_name, extra_context=context)
        if agent is None:
            return f"Error: failed to add '{agent_name}'"

        return (
            f"Added '{agent_name}' to the team.\n"
            f"Role: {agent.role}\n"
            f"Model: {agent.model}\n"
            f"You can now delegate tasks to @{agent_name} using message_agent."
        )

    def _remove_agent(self, agent_name: str) -> str:
        if not agent_name:
            return "Error: agent_name is required for remove_agent"

        if agent_name == "lead":
            return "Error: cannot remove the team lead."

        if agent_name not in self._team.agents:
            current = ", ".join(n for n in self._team.agents if n != "lead")
            return (
                f"Error: '{agent_name}' is not on the team. Current members: {current or '(none)'}"
            )

        self._team.remove_agent(agent_name)
        return f"Removed '{agent_name}' from the team."

    def _update_context(self, agent_name: str, context: str) -> str:
        if not agent_name:
            return "Error: agent_name is required for update_context"
        if not context:
            return "Error: context is required for update_context"

        if agent_name not in self._team.agents:
            return f"Error: '{agent_name}' is not on the team."

        # Update config
        agent_cfg = self._team.config.team.agents.get(agent_name)
        if agent_cfg:
            agent_cfg.extra_context = context

        # Recreate agent with updated context (system prompt is built at creation time)
        from cadre.agents.presets import PRESET_FACTORIES

        factory = PRESET_FACTORIES.get(agent_name)
        if factory:
            new_agent = factory(self._team.config)
            # Preserve the old agent's tools list structure (messaging tool)
            from cadre.tools.messaging import MessageAgentTool

            old_agent = self._team.agents[agent_name]
            for tool in old_agent.tools:
                if isinstance(tool, MessageAgentTool):
                    new_agent.tools.append(tool)
                    break
            self._team.agents[agent_name] = new_agent
            from cadre.agents.loop import AgentLoop

            self._team._loops[agent_name] = AgentLoop(new_agent, self._team.provider)

        # Persist
        self._team.config.save_agent(agent_name)

        return f"Updated context for '{agent_name}'."
