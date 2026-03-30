"""Tests for CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from cadre.cli import main


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_models_list():
    runner = CliRunner()
    result = runner.invoke(main, ["models", "list"])
    assert result.exit_code == 0
    assert "claude" in result.output.lower() or "Benchmark" in result.output


def test_models_benchmarks():
    runner = CliRunner()
    result = runner.invoke(main, ["models", "benchmarks"])
    assert result.exit_code == 0
    assert "claude" in result.output.lower() or "Benchmark" in result.output


def test_models_show_no_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["models"])
    assert result.exit_code == 0
    assert "No configuration found" in result.output


def test_workflow_list():
    runner = CliRunner()
    result = runner.invoke(main, ["workflow", "list"])
    assert result.exit_code == 0
    assert "design-implement-review" in result.output


def test_doctor():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output


def test_status_no_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "No configuration found" in result.output


def test_config_show_no_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["config", "show"])
    assert result.exit_code == 0
    assert "No configuration found" in result.output


def test_keys_show():
    runner = CliRunner()
    result = runner.invoke(main, ["keys", "show"])
    assert result.exit_code == 0
    assert "API Keys" in result.output
    assert "anthropic" in result.output


def test_keys_set_and_show():
    runner = CliRunner()
    import os

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["keys", "set", "anthropic", "sk-test-key-12345678"])
        assert result.exit_code == 0
        assert "saved" in result.output
        # Clean up
        os.environ.pop("ANTHROPIC_API_KEY", None)
