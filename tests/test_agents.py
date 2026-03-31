"""Tests for agent manager."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cadre.agents.manager import (
    AgentInfo,
    _agent_to_markdown,
    _parse_frontmatter,
    delete_agent,
    install_preset,
    install_team,
    list_agents,
    load_agent,
    save_agent,
)


def test_parse_frontmatter():
    content = """---
name: test
description: A test agent
model: sonnet
tools: Read, Write, Bash
maxTurns: 10
---

You are a test agent."""

    fm, body = _parse_frontmatter(content)
    assert fm["name"] == "test"
    assert fm["description"] == "A test agent"
    assert fm["model"] == "sonnet"
    assert fm["tools"] == "Read, Write, Bash"
    assert fm["maxTurns"] == "10"
    assert body == "You are a test agent."


def test_parse_frontmatter_no_frontmatter():
    fm, body = _parse_frontmatter("Just plain text")
    assert fm == {}
    assert body == "Just plain text"


def test_agent_to_markdown():
    agent = AgentInfo(
        name="test",
        description="A test agent",
        model="sonnet",
        tools=["Read", "Write"],
        max_turns=10,
        system_prompt="You are a test agent.",
    )
    md = _agent_to_markdown(agent)
    assert "name: test" in md
    assert "description: A test agent" in md
    assert "model: sonnet" in md
    assert "tools: Read, Write" in md
    assert "maxTurns: 10" in md
    assert "You are a test agent." in md


def test_save_and_load_agent():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = AgentInfo(
            name="test",
            description="Test agent",
            model="haiku",
            tools=["Read"],
            system_prompt="Hello",
        )
        save_agent(agent, Path(tmpdir))
        loaded = load_agent("test", Path(tmpdir))
        assert loaded.name == "test"
        assert loaded.description == "Test agent"
        assert loaded.model == "haiku"
        assert loaded.tools == ["Read"]
        assert loaded.system_prompt == "Hello"


def test_list_agents():
    with tempfile.TemporaryDirectory() as tmpdir:
        # No agents dir yet
        agents = list_agents(Path(tmpdir))
        assert agents == []

        # Create one
        save_agent(
            AgentInfo(name="a", description="Agent A", system_prompt="A"),
            Path(tmpdir),
        )
        agents = list_agents(Path(tmpdir))
        assert len(agents) == 1
        assert agents[0].name == "a"


def test_delete_agent():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_agent(
            AgentInfo(name="deleteme", system_prompt=""),
            Path(tmpdir),
        )
        assert len(list_agents(Path(tmpdir))) == 1
        delete_agent("deleteme", Path(tmpdir))
        assert len(list_agents(Path(tmpdir))) == 0


def test_install_preset():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = install_preset("lead", Path(tmpdir))
        assert agent.name == "lead"
        assert agent.description != ""
        assert (Path(tmpdir) / ".claude" / "agents" / "lead.md").exists()


def test_install_team():
    with tempfile.TemporaryDirectory() as tmpdir:
        agents = install_team("full", Path(tmpdir))
        assert len(agents) == 4
        names = {a.name for a in agents}
        assert names == {"lead", "engineer", "architect", "qa"}
