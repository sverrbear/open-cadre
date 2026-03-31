"""Tests for message router."""

from __future__ import annotations

from cadre.orchestrator.router import MessageRouter
from cadre.orchestrator.team import Team


def test_parse_mention(sample_config):
    team = Team(config=sample_config)
    team.setup()
    router = MessageRouter(team=team)

    assert router._parse_mention("@analytics_engineer write a model") == "analytics_engineer"
    assert router._parse_mention("@data_architect design something") == "data_architect"
    assert router._parse_mention("just a regular message") is None
    assert router._parse_mention("@nonexistent do something") is None


def test_default_agent_full_mode(sample_config):
    team = Team(config=sample_config)
    team.setup()
    router = MessageRouter(team=team)
    assert router._get_default_agent() == "lead"


def test_default_agent_solo_mode(solo_config):
    team = Team(config=solo_config)
    team.setup()
    router = MessageRouter(team=team)
    assert router._get_default_agent() == "solo"
