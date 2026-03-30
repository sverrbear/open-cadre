"""Tests for provider registry."""

from __future__ import annotations

from cadre.providers.registry import ModelCatalog, ProviderRegistry


def test_provider_registry():
    registry = ProviderRegistry()
    registry.add_provider("anthropic", api_key="test-key")
    registry.add_provider("ollama", api_base="http://localhost:11434")

    assert "anthropic" in registry.available_providers()
    assert registry.get_api_keys() == {"anthropic": "test-key"}
    assert registry.get_api_bases() == {"ollama": "http://localhost:11434"}


def test_model_catalog():
    catalog = ModelCatalog.load()
    assert len(catalog.models) > 0
    assert "anthropic/claude-opus-4-6" in catalog.models


def test_model_catalog_strategies():
    catalog = ModelCatalog.load()
    balanced = catalog.get_strategy("balanced")
    assert balanced is not None
    assert "lead" in balanced


def test_model_catalog_list():
    catalog = ModelCatalog.load()
    models = catalog.list_models()
    assert len(models) > 0
    # Should be sorted by SQL accuracy descending
    assert models[0].sql_accuracy >= models[-1].sql_accuracy
