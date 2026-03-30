"""Tests for the messaging tool (peer-to-peer agent communication)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cadre.agents.base import AgentEvent
from cadre.tools.messaging import MAX_DELEGATION_DEPTH, MessageAgentTool, _message_depth


def test_schema_excludes_self():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect", "engineer"])
    schema = tool.to_schema()
    enum = schema["function"]["parameters"]["properties"]["agent"]["enum"]
    assert "lead" not in enum
    assert "architect" in enum
    assert "engineer" in enum


def test_schema_required_fields():
    tool = MessageAgentTool(agent_name="qa", team_agent_names=["lead", "qa"])
    schema = tool.to_schema()
    assert schema["function"]["parameters"]["required"] == ["agent", "message"]


@pytest.mark.asyncio
async def test_execute_without_router():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])
    result = await tool.execute({"agent": "architect", "message": "hello"})
    assert "Error" in result
    assert "router" in result


@pytest.mark.asyncio
async def test_execute_unknown_agent():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])
    tool._router = MagicMock()
    result = await tool.execute({"agent": "unknown", "message": "hello"})
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_execute_message_self():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])
    tool._router = MagicMock()
    result = await tool.execute({"agent": "lead", "message": "hello"})
    assert "Error" in result
    assert "yourself" in result


@pytest.mark.asyncio
async def test_execute_missing_fields():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])
    tool._router = MagicMock()
    result = await tool.execute({"agent": "", "message": ""})
    assert "Error" in result
    assert "required" in result


@pytest.mark.asyncio
async def test_execute_success():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])

    async def mock_send(agent_name, message):
        yield AgentEvent(type="content_delta", content="partial ")
        yield AgentEvent(type="response", content="Here is my design.")

    router = MagicMock()
    router.send_to_agent = mock_send
    tool.set_router(router)

    result = await tool.execute({"agent": "architect", "message": "Design a model"})
    assert result == "Here is my design."


@pytest.mark.asyncio
async def test_execute_no_response():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])

    async def mock_send(agent_name, message):
        yield AgentEvent(type="error", content="something went wrong")

    router = MagicMock()
    router.send_to_agent = mock_send
    tool.set_router(router)

    result = await tool.execute({"agent": "architect", "message": "hello"})
    assert result == "(no response received)"


@pytest.mark.asyncio
async def test_depth_limit():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])
    tool._router = MagicMock()

    # Simulate being at max depth
    token = _message_depth.set(MAX_DELEGATION_DEPTH)
    try:
        result = await tool.execute({"agent": "architect", "message": "hello"})
        assert "Error" in result
        assert "depth" in result
    finally:
        _message_depth.reset(token)


@pytest.mark.asyncio
async def test_depth_resets_after_call():
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])

    async def mock_send(agent_name, message):
        yield AgentEvent(type="response", content="ok")

    router = MagicMock()
    router.send_to_agent = mock_send
    tool.set_router(router)

    assert _message_depth.get() == 0
    await tool.execute({"agent": "architect", "message": "hello"})
    assert _message_depth.get() == 0


@pytest.mark.asyncio
async def test_message_prefixed_with_sender():
    """Verify the message sent to the router includes sender context."""
    tool = MessageAgentTool(agent_name="lead", team_agent_names=["lead", "architect"])

    sent_messages = []

    async def mock_send(agent_name, message):
        sent_messages.append((agent_name, message))
        yield AgentEvent(type="response", content="ok")

    router = MagicMock()
    router.send_to_agent = mock_send
    tool.set_router(router)

    await tool.execute({"agent": "architect", "message": "Design a user model"})
    assert len(sent_messages) == 1
    assert sent_messages[0][0] == "architect"
    assert "[Message from lead]" in sent_messages[0][1]
    assert "Design a user model" in sent_messages[0][1]
