"""Tests for AgentSession and StreamEvent parsing."""

from __future__ import annotations

from cadre.agents.session import AgentSession, StreamEvent, parse_stream_event
from cadre.tui.screens.chat_settings import ChatSessionSettings


def test_parse_stream_event_assistant():
    """Parse an assistant event with text and usage."""
    event = {
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "Hello world"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    }
    se = parse_stream_event("lead", event)
    assert se.agent_name == "lead"
    assert se.event_type == "assistant"
    assert se.text == "Hello world"
    assert se.input_tokens == 10
    assert se.output_tokens == 5


def test_parse_stream_event_content_block_delta():
    """Parse a content_block_delta event."""
    event = {
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "chunk"},
    }
    se = parse_stream_event("engineer", event)
    assert se.event_type == "content_block_delta"
    assert se.text == "chunk"


def test_parse_stream_event_tool_use():
    """Parse a tool_use event."""
    event = {
        "type": "tool_use",
        "name": "Bash",
        "input": {"command": "pytest tests/"},
    }
    se = parse_stream_event("qa", event)
    assert se.event_type == "tool_use"
    assert se.tool_name == "Bash"
    assert "pytest" in se.tool_input_summary


def test_parse_stream_event_result():
    """Parse a result event with session_id and usage."""
    event = {
        "type": "result",
        "result": "Done.",
        "session_id": "abc-123",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    se = parse_stream_event("architect", event)
    assert se.event_type == "result"
    assert se.result_text == "Done."
    assert se.session_id == "abc-123"
    assert se.input_tokens == 100
    assert se.output_tokens == 50


def test_parse_stream_event_unknown_type():
    """Unknown event types should parse without error."""
    event = {"type": "unknown_event", "data": "something"}
    se = parse_stream_event("lead", event)
    assert se.event_type == "unknown_event"
    assert se.text == ""


def test_agent_session_build_cmd():
    """Test command building with various settings."""
    session = AgentSession(
        agent_name="engineer",
        settings=ChatSessionSettings(
            model="sonnet",
            effort="high",
            permission_mode="plan",
        ),
    )
    cmd = session._build_cmd("fix the bug")
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "fix the bug" in cmd
    assert "--agent" in cmd
    assert "engineer" in cmd
    assert "--model" in cmd
    assert "sonnet" in cmd
    assert "--effort" in cmd
    assert "high" in cmd
    assert "--permission-mode" in cmd
    assert "plan" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd


def test_agent_session_build_cmd_with_resume():
    """Test command includes --resume when session_id is set."""
    session = AgentSession(agent_name="lead")
    session.session_id = "sess-456"
    cmd = session._build_cmd("hello")
    assert "--resume" in cmd
    assert "sess-456" in cmd


def test_agent_session_build_cmd_skip_permissions():
    """Test --dangerously-skip-permissions flag."""
    session = AgentSession(
        agent_name="lead",
        settings=ChatSessionSettings(skip_permissions=True),
    )
    cmd = session._build_cmd("test")
    assert "--dangerously-skip-permissions" in cmd


def test_agent_session_initial_state():
    """Test initial state of a new AgentSession."""
    session = AgentSession(agent_name="qa")
    assert session.agent_name == "qa"
    assert session.status == "idle"
    assert session.session_id is None
    assert session.total_input_tokens == 0
    assert session.total_output_tokens == 0
    assert not session.is_active


def test_agent_session_process_event_tracks_tokens():
    """Test that _process_event accumulates tokens."""
    session = AgentSession(agent_name="lead")
    se = StreamEvent(
        agent_name="lead",
        event_type="assistant",
        text="hello",
        input_tokens=10,
        output_tokens=5,
    )
    session._process_event(se)
    assert session.total_input_tokens == 10
    assert session.total_output_tokens == 5
    assert session.accumulated_text == "hello"


def test_agent_session_process_event_captures_session_id():
    """Test that result events capture session_id."""
    session = AgentSession(agent_name="lead")
    se = StreamEvent(
        agent_name="lead",
        event_type="result",
        session_id="new-session",
        input_tokens=50,
        output_tokens=25,
    )
    session._process_event(se)
    assert session.session_id == "new-session"


def test_agent_session_process_event_tool_use_updates_status():
    """Test that tool_use events update status to working."""
    session = AgentSession(agent_name="engineer")
    se = StreamEvent(
        agent_name="engineer",
        event_type="tool_use",
        tool_name="Edit",
        tool_input_summary="src/main.py",
    )
    session._process_event(se)
    assert session.status == "working"
    assert "Edit" in session.current_task
