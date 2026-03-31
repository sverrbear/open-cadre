"""Tests for configuration system."""

from __future__ import annotations

import tempfile

from cadre.config import CadreConfig


def test_default_config():
    config = CadreConfig()
    assert config.project.name == "My Project"
    assert config.team.mode == "full"
    assert config.team.preset == "full"


def test_save_and_load():
    config = CadreConfig()
    config.project.name = "Test"
    with tempfile.TemporaryDirectory() as tmpdir:
        config.save(tmpdir)
        loaded = CadreConfig.load(tmpdir)
        assert loaded.project.name == "Test"
        assert loaded.team.mode == "full"


def test_load_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = CadreConfig.load(tmpdir)
        assert config.project.name == "My Project"


def test_ui_config():
    config = CadreConfig()
    assert config.ui.theme == "dark"
    assert config.ui.sidebar_visible is True
