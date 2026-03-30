"""Tests for API key management (cadre.env operations)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cadre.keys import (
    ENV_FILE,
    PROVIDER_ENV_VARS,
    check_key_for_model,
    generate_env_file,
    get_env_path,
    get_provider_for_model,
    key_remove,
    key_set,
    load_env,
    show_keys,
)


def test_get_env_path():
    p = get_env_path(Path("/tmp/test"))
    assert p == Path("/tmp/test") / ENV_FILE


def test_generate_env_file_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_env_file(Path(tmpdir))
        assert path.exists()
        content = path.read_text()
        assert "OpenCadre API Keys" in content
        assert "# ANTHROPIC_API_KEY=" in content
        assert "# OPENAI_API_KEY=" in content
        assert "# GOOGLE_API_KEY=" in content


def test_generate_env_file_with_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_env_file(Path(tmpdir), keys={"anthropic": "sk-test-key"})
        content = path.read_text()
        assert "ANTHROPIC_API_KEY=sk-test-key" in content
        assert "# OPENAI_API_KEY=" in content


def test_key_set_and_show():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        key_set(base, provider="anthropic", value="sk-ant-test123")
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test123"

        keys = show_keys(base)
        assert keys["anthropic"] is not None
        assert "sk-a" in keys["anthropic"]  # masked starts with first 4 chars

        # Cleanup
        os.environ.pop("ANTHROPIC_API_KEY", None)


def test_key_remove():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        key_set(base, provider="openai", value="sk-test-openai")
        key_remove(base, provider="openai")
        assert os.environ.get("OPENAI_API_KEY") is None


def test_load_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        env_path = base / ENV_FILE
        env_path.write_text("TEST_CADRE_LOAD=loaded-value\n")

        load_env(base)
        assert os.environ.get("TEST_CADRE_LOAD") == "loaded-value"
        os.environ.pop("TEST_CADRE_LOAD", None)


def test_load_env_does_not_override():
    os.environ["TEST_CADRE_NOOVERRIDE"] = "original"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            env_path = base / ENV_FILE
            env_path.write_text("TEST_CADRE_NOOVERRIDE=new-value\n")

            load_env(base)
            assert os.environ["TEST_CADRE_NOOVERRIDE"] == "original"
    finally:
        os.environ.pop("TEST_CADRE_NOOVERRIDE", None)


def test_get_provider_for_model():
    assert get_provider_for_model("anthropic/claude-sonnet-4-6") == "anthropic"
    assert get_provider_for_model("openai/gpt-4o") == "openai"
    assert get_provider_for_model("ollama/llama3.3-70b") == "ollama"
    assert get_provider_for_model("local-model") is None


def test_check_key_for_model_ollama():
    # Ollama never needs a key
    assert check_key_for_model("ollama/llama3.3-70b") is True


def test_check_key_for_model_missing():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with tempfile.TemporaryDirectory() as tmpdir:
        assert check_key_for_model("anthropic/claude-sonnet-4-6", Path(tmpdir)) is False


def test_check_key_for_model_present():
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    try:
        assert check_key_for_model("anthropic/claude-sonnet-4-6") is True
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)


def test_provider_env_vars_complete():
    """Ensure all expected providers are mapped."""
    assert "anthropic" in PROVIDER_ENV_VARS
    assert "openai" in PROVIDER_ENV_VARS
    assert "google" in PROVIDER_ENV_VARS
