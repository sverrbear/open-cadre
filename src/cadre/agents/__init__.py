"""Agent management — CRUD for .claude/agents/*.md files."""

from cadre.agents.manager import AgentInfo, list_agents, load_agent, save_agent

__all__ = ["AgentInfo", "list_agents", "load_agent", "save_agent"]
