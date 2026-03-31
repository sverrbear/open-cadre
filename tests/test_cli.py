"""Tests for CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from cadre.cli import main


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_doctor():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output


def test_agents_no_agents():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["agents"])
    assert result.exit_code == 0
    assert "No agents" in result.output


def test_init_and_agents():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "full"])
        assert result.exit_code == 0
        assert "Installed" in result.output

        result = runner.invoke(main, ["agents"])
        assert result.exit_code == 0
        assert "lead" in result.output
        assert "engineer" in result.output


def test_init_invalid_preset():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "nonexistent"])
    assert result.exit_code == 0
    assert "Unknown preset" in result.output
