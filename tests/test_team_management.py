"""Tests for team management tool and runtime team modification."""

from __future__ import annotations

import pytest

from cadre.agents.presets import PRESET_FACTORIES
from cadre.config import AgentConfig, CadreConfig, ProjectConfig, ProviderConfig, TeamConfig
from cadre.tools.team_management import TeamManagementTool


@pytest.fixture
def lead_config() -> CadreConfig:
    """Config with only a lead agent."""
    return CadreConfig(
        project=ProjectConfig(name="Test Project", type="generic"),
        providers={"anthropic": ProviderConfig(api_key="test-key")},
        team=TeamConfig(
            mode="full",
            agents={"lead": AgentConfig(model="anthropic/claude-opus-4-6")},
        ),
    )


@pytest.fixture
def tool_with_team(lead_config):
    """Create a TeamManagementTool with a real Team attached."""
    from cadre.orchestrator.team import Team
    from cadre.providers.litellm_provider import LiteLLMProvider

    team = Team(config=lead_config)
    # Manually create lead agent without full setup (avoids provider resolution)
    factory = PRESET_FACTORIES["lead"]
    agent = factory(lead_config)
    team.agents["lead"] = agent
    from cadre.agents.loop import AgentLoop

    team.provider = LiteLLMProvider(api_keys={"anthropic": "test-key"})
    team._loops["lead"] = AgentLoop(agent, team.provider)

    tool = TeamManagementTool()
    tool.set_team(team)
    return tool, team


@pytest.mark.asyncio
async def test_list_presets(tool_with_team):
    tool, _team = tool_with_team
    result = await tool.execute({"action": "list_presets"})
    assert "backend" in result
    assert "frontend" in result
    assert "data_architect" in result
    assert "analytics_engineer" in result
    assert "data_qa" in result
    assert "qa" in result


@pytest.mark.asyncio
async def test_list_team(tool_with_team):
    tool, _team = tool_with_team
    result = await tool.execute({"action": "list_team"})
    assert "lead" in result


@pytest.mark.asyncio
async def test_add_agent(tool_with_team):
    tool, team = tool_with_team
    result = await tool.execute(
        {
            "action": "add_agent",
            "agent_name": "backend",
            "context": "Python FastAPI project",
        }
    )
    assert "Added" in result
    assert "backend" in team.agents
    assert team.agents["backend"].name == "backend"


@pytest.mark.asyncio
async def test_add_agent_already_on_team(tool_with_team):
    tool, _team = tool_with_team
    await tool.execute({"action": "add_agent", "agent_name": "backend"})
    result = await tool.execute({"action": "add_agent", "agent_name": "backend"})
    assert "already on the team" in result


@pytest.mark.asyncio
async def test_add_invalid_preset(tool_with_team):
    tool, _team = tool_with_team
    result = await tool.execute({"action": "add_agent", "agent_name": "nonexistent"})
    assert "Error" in result
    assert "not a valid" in result


@pytest.mark.asyncio
async def test_remove_agent(tool_with_team):
    tool, team = tool_with_team
    await tool.execute({"action": "add_agent", "agent_name": "backend"})
    assert "backend" in team.agents
    result = await tool.execute({"action": "remove_agent", "agent_name": "backend"})
    assert "Removed" in result
    assert "backend" not in team.agents


@pytest.mark.asyncio
async def test_cannot_remove_lead(tool_with_team):
    tool, team = tool_with_team
    result = await tool.execute({"action": "remove_agent", "agent_name": "lead"})
    assert "cannot remove" in result.lower()
    assert "lead" in team.agents


@pytest.mark.asyncio
async def test_remove_nonexistent_agent(tool_with_team):
    tool, _team = tool_with_team
    result = await tool.execute({"action": "remove_agent", "agent_name": "frontend"})
    assert "not on the team" in result


@pytest.mark.asyncio
async def test_add_agent_missing_name(tool_with_team):
    tool, _team = tool_with_team
    result = await tool.execute({"action": "add_agent"})
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_messaging_updated_on_add(tool_with_team):
    """After adding an agent, existing agents should be able to message the new one."""
    tool, team = tool_with_team
    await tool.execute({"action": "add_agent", "agent_name": "backend"})

    from cadre.tools.messaging import MessageAgentTool

    # Check lead's messaging tool includes backend
    lead = team.agents["lead"]
    msg_tool = None
    for t in lead.tools:
        if isinstance(t, MessageAgentTool):
            msg_tool = t
            break
    assert msg_tool is not None
    assert "backend" in msg_tool._team_agent_names

    # Check backend's messaging tool includes lead
    backend = team.agents["backend"]
    msg_tool = None
    for t in backend.tools:
        if isinstance(t, MessageAgentTool):
            msg_tool = t
            break
    assert msg_tool is not None
    assert "lead" in msg_tool._team_agent_names


@pytest.mark.asyncio
async def test_messaging_updated_on_remove(tool_with_team):
    """After removing an agent, remaining agents' messaging should not include it."""
    tool, team = tool_with_team
    await tool.execute({"action": "add_agent", "agent_name": "backend"})
    await tool.execute({"action": "add_agent", "agent_name": "frontend"})
    await tool.execute({"action": "remove_agent", "agent_name": "backend"})

    from cadre.tools.messaging import MessageAgentTool

    # Check lead's messaging tool does NOT include backend
    lead = team.agents["lead"]
    for t in lead.tools:
        if isinstance(t, MessageAgentTool):
            assert "backend" not in t._team_agent_names
            assert "frontend" in t._team_agent_names
            break
