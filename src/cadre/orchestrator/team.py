"""Team manager — creates, starts, and manages agent lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cadre.agents.base import Agent, AgentStatus

if TYPE_CHECKING:
    from cadre.orchestrator.router import MessageRouter
from cadre.agents.loop import AgentLoop
from cadre.agents.presets import PRESET_FACTORIES
from cadre.config import CadreConfig
from cadre.providers.litellm_provider import LiteLLMProvider
from cadre.providers.registry import ProviderRegistry


@dataclass
class Team:
    """Manages the team of agents."""

    config: CadreConfig
    agents: dict[str, Agent] = field(default_factory=dict)
    provider: LiteLLMProvider | None = None
    _loops: dict[str, AgentLoop] = field(default_factory=dict)

    def setup(self) -> None:
        """Initialize provider and create agents from config."""
        import os
        import re

        from cadre.keys import PROVIDER_ENV_VARS

        def _resolve_key(value: str | None) -> str | None:
            """Resolve ${ENV_VAR} references to actual values."""
            if not value:
                return value
            m = re.fullmatch(r"\$\{(\w+)\}", value)
            if m:
                return os.environ.get(m.group(1))
            return value

        # Setup provider
        registry = ProviderRegistry()
        configured_providers: set[str] = set()
        for name, pcfg in self.config.providers.items():
            resolved_key = _resolve_key(pcfg.api_key)
            # Fall back to env var if the reference didn't resolve
            if not resolved_key:
                env_var = PROVIDER_ENV_VARS.get(name)
                if env_var:
                    resolved_key = os.environ.get(env_var)
            registry.add_provider(
                name,
                api_key=resolved_key,
                api_base=pcfg.api_base,
            )
            configured_providers.add(name)

        # Also pick up providers from environment that aren't in config
        for provider, env_var in PROVIDER_ENV_VARS.items():
            if provider not in configured_providers:
                key = os.environ.get(env_var)
                if key:
                    registry.add_provider(provider, api_key=key)

        self.provider = LiteLLMProvider(
            api_keys=registry.get_api_keys(),
            api_bases=registry.get_api_bases(),
        )

        # Create agents
        enabled = self.config.get_enabled_agents()
        for agent_name in enabled:
            factory = PRESET_FACTORIES.get(agent_name)
            if factory:
                agent = factory(self.config)
                self.agents[agent_name] = agent
                self._loops[agent_name] = AgentLoop(agent, self.provider)

        # Add messaging tools for team mode (not solo)
        if "solo" not in self.agents:
            from cadre.tools.messaging import MessageAgentTool

            team_names = list(self.agents.keys())
            for name, agent in self.agents.items():
                agent.tools.append(MessageAgentTool(agent_name=name, team_agent_names=team_names))

    def inject_router(self, router: MessageRouter) -> None:
        """Inject router reference into MessageAgentTools for peer communication."""
        from cadre.tools.messaging import MessageAgentTool

        for agent in self.agents.values():
            for tool in agent.tools:
                if isinstance(tool, MessageAgentTool):
                    tool.set_router(router)

    def get_agent(self, name: str) -> Agent | None:
        return self.agents.get(name)

    def get_loop(self, name: str) -> AgentLoop | None:
        return self._loops.get(name)

    def list_agents(self) -> list[Agent]:
        return list(self.agents.values())

    def get_status(self) -> dict[str, dict[str, str]]:
        """Get status of all agents."""
        return {
            name: {
                "role": agent.role,
                "model": agent.model,
                "status": agent.status.value,
            }
            for name, agent in self.agents.items()
        }

    def shutdown(self) -> None:
        """Reset all agents."""
        for agent in self.agents.values():
            agent.clear_history()
            agent.status = AgentStatus.IDLE
