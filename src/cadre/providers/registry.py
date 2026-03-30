"""Provider registry and model catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass
class ModelInfo:
    """Information about a specific model."""

    id: str
    provider: str
    name: str
    sql_accuracy: float
    coding_score: float
    tool_calling: float
    cost_input_1m: float
    cost_output_1m: float
    speed: str
    best_for: list[str]


@dataclass
class ModelCatalog:
    """Catalog of available models with benchmark data."""

    models: dict[str, ModelInfo] = field(default_factory=dict)
    strategies: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load(cls) -> ModelCatalog:
        """Load benchmark data from the bundled JSON file."""
        benchmark_path = Path(__file__).parent.parent / "benchmarks" / "models.json"
        with open(benchmark_path) as f:
            data = json.load(f)

        catalog = cls()
        for model_id, info in data.get("models", {}).items():
            catalog.models[model_id] = ModelInfo(id=model_id, **info)
        catalog.strategies = data.get("strategies", {})
        return catalog

    def get_strategy(self, name: str) -> dict[str, str] | None:
        """Get model assignments for a named strategy."""
        return self.strategies.get(name)

    def get_model(self, model_id: str) -> ModelInfo | None:
        """Get info for a specific model."""
        return self.models.get(model_id)

    def list_models(self) -> list[ModelInfo]:
        """List all models sorted by SQL accuracy descending."""
        return sorted(self.models.values(), key=lambda m: m.sql_accuracy, reverse=True)


@dataclass
class ProviderRegistry:
    """Registry of configured providers and their API keys."""

    providers: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_provider(self, name: str, api_key: str | None = None, api_base: str | None = None):
        config: dict[str, str] = {}
        if api_key:
            config["api_key"] = api_key
        if api_base:
            config["api_base"] = api_base
        self.providers[name] = config

    def get_api_keys(self) -> dict[str, str]:
        return {name: cfg["api_key"] for name, cfg in self.providers.items() if "api_key" in cfg}

    def get_api_bases(self) -> dict[str, str]:
        return {name: cfg["api_base"] for name, cfg in self.providers.items() if "api_base" in cfg}

    def available_providers(self) -> list[str]:
        return list(self.providers.keys())
