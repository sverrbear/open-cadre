"""Tests for agent creation and configuration."""

from __future__ import annotations

from cadre.agents.base import Agent, AgentStatus
from cadre.agents.presets import PRESET_FACTORIES
from cadre.tools.file_ops import FileReadTool


def test_agent_creation():
    agent = Agent(
        name="test",
        role="Test agent",
        system_prompt="You are a test agent.",
        model="anthropic/claude-sonnet-4-6",
    )
    assert agent.name == "test"
    assert agent.status == AgentStatus.IDLE
    assert agent.history == []


def test_agent_tool_schemas():
    tool = FileReadTool()
    agent = Agent(
        name="test",
        role="Test",
        system_prompt="test",
        model="test",
        tools=[tool],
    )
    schemas = agent.get_tool_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "file_read"


def test_agent_history():
    agent = Agent(name="test", role="Test", system_prompt="test", model="test")
    agent.add_message("user", "hello")
    assert len(agent.history) == 1
    assert agent.history[0]["role"] == "user"
    agent.clear_history()
    assert len(agent.history) == 0


def test_agent_find_tool():
    tool = FileReadTool()
    agent = Agent(name="test", role="Test", system_prompt="test", model="test", tools=[tool])
    assert agent.get_tool("file_read") is not None
    assert agent.get_tool("nonexistent") is None


def test_preset_factories(sample_config):
    for name, factory in PRESET_FACTORIES.items():
        if name == "solo":
            continue  # solo needs solo config
        agent = factory(sample_config)
        assert agent.name == name
        assert agent.model != ""
        assert len(agent.tools) > 0
        assert len(agent.get_tool_schemas()) > 0


def test_solo_preset(solo_config):
    factory = PRESET_FACTORIES["solo"]
    agent = factory(solo_config)
    assert agent.name == "solo"
    assert agent.can_write_code is True
