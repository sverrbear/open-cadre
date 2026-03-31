"""Tests for TeamRouter — @mention parsing, routing, team management."""

from __future__ import annotations

from cadre.agents.manager import AgentInfo
from cadre.agents.router import TeamMessage, TeamRouter


def _make_agents() -> list[AgentInfo]:
    """Create test agent infos."""
    return [
        AgentInfo(name="lead", model="opus", effort="high"),
        AgentInfo(name="engineer", model="sonnet", effort="high"),
        AgentInfo(name="architect", model="opus", effort="high"),
        AgentInfo(name="qa", model="sonnet", effort="high"),
    ]


def test_router_start_team():
    """Test that start_team creates sessions for all agents."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    assert router.team_name == "full"
    assert set(router.sessions.keys()) == {"lead", "engineer", "architect", "qa"}
    assert router.agent_names == {"lead", "engineer", "architect", "qa"}


def test_router_parse_mentions_single():
    """Test parsing a single @mention."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    text = "@engineer fix the null check in auth.py"
    mentions = router._parse_mentions(text)
    assert len(mentions) == 1
    assert mentions[0][0] == "engineer"
    assert "null check" in mentions[0][1]


def test_router_parse_mentions_multiple():
    """Test parsing multiple @mentions."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    text = "@engineer implement the feature\n@qa review the changes after"
    mentions = router._parse_mentions(text)
    assert len(mentions) == 2
    assert mentions[0][0] == "engineer"
    assert mentions[1][0] == "qa"


def test_router_parse_mentions_no_match():
    """Test that non-team @mentions are ignored."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    text = "@designer make it look nice"
    mentions = router._parse_mentions(text)
    assert len(mentions) == 0


def test_router_parse_mentions_empty_message():
    """Test that @mentions with no message body are ignored."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    text = "Some text without mentions"
    mentions = router._parse_mentions(text)
    assert len(mentions) == 0


def test_router_parse_mentions_inline():
    """Test @mention embedded in longer text."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    text = "I've analyzed the issue. @engineer please fix src/auth.py line 42"
    mentions = router._parse_mentions(text)
    assert len(mentions) == 1
    assert mentions[0][0] == "engineer"
    assert "fix src/auth.py" in mentions[0][1]


def test_router_get_session():
    """Test getting sessions by name."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    assert router.get_session("lead") is not None
    assert router.get_session("nonexistent") is None


def test_router_message_callback():
    """Test that on_message callback is called for team messages."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    messages: list[TeamMessage] = []
    router.on_message = lambda msg: messages.append(msg)

    # Route to non-existent agent
    router._route_message("lead", "nonexistent", "do something", 0)
    assert len(messages) == 1
    assert messages[0].message_type == "system"
    assert "not in this team" in messages[0].content


def test_router_routing_depth_limit():
    """Test that routing stops at MAX_ROUTING_DEPTH."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)

    messages: list[TeamMessage] = []
    router.on_message = lambda msg: messages.append(msg)

    # Simulate deep routing chain
    router._routing_depth["lead"] = 15  # over the limit

    router._handle_agent_complete("lead", "@engineer do the thing")

    # Should get a system message about depth limit
    system_msgs = [m for m in messages if m.message_type == "system"]
    assert len(system_msgs) == 1
    assert "depth limit" in system_msgs[0].content.lower()


def test_router_stop_all():
    """Test that stop_all doesn't crash with no active processes."""
    router = TeamRouter()
    agents = _make_agents()
    router.start_team("full", agents)
    router.stop_all()  # Should not raise


def test_router_session_settings():
    """Test that agent settings are applied to sessions."""
    router = TeamRouter()
    agents = [
        AgentInfo(name="lead", model="opus", effort="high", permission_mode="plan"),
    ]
    router.start_team("test", agents)

    session = router.get_session("lead")
    assert session is not None
    assert session.settings.model == "opus"
    assert session.settings.effort == "high"
    assert session.settings.permission_mode == "plan"
