"""Load and query benchmark data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


class BenchmarkData:
    """Model benchmark data for data engineering tasks."""

    def __init__(self) -> None:
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        path = Path(__file__).parent / "models.json"
        with open(path) as f:
            return json.load(f)

    def get_models(self) -> dict[str, Any]:
        return self.data.get("models", {})

    def get_strategies(self) -> dict[str, Any]:
        return self.data.get("strategies", {})

    def render_table(self, console: Console | None = None) -> None:
        """Render benchmark table to terminal."""
        if console is None:
            console = Console()

        table = Table(
            title="Model Benchmarks (data engineering tasks)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Model", style="cyan", min_width=30)
        table.add_column("SQL", justify="right")
        table.add_column("Code", justify="right")
        table.add_column("Tools", justify="right")
        table.add_column("Speed")
        table.add_column("Cost/1M", justify="right")

        models = self.get_models()
        # Sort by SQL accuracy descending
        sorted_models = sorted(models.items(), key=lambda x: x[1]["sql_accuracy"], reverse=True)

        for model_id, info in sorted_models:
            cost_in = info["cost_input_1m"]
            cost_out = info["cost_output_1m"]
            cost_str = "free" if cost_in == 0 else f"${cost_in}/${cost_out}"

            table.add_row(
                model_id,
                f".{int(info['sql_accuracy'] * 100) % 100:02d}" if info["sql_accuracy"] < 1 else "1.0",
                f".{int(info['coding_score'] * 100) % 100:02d}" if info["coding_score"] < 1 else "1.0",
                f".{int(info['tool_calling'] * 100) % 100:02d}" if info["tool_calling"] < 1 else "1.0",
                info["speed"],
                cost_str,
            )

        console.print(table)

    def render_strategies(self, console: Console | None = None) -> None:
        """Render strategy comparison."""
        if console is None:
            console = Console()

        table = Table(title="Model Strategies", show_header=True, header_style="bold")
        table.add_column("Strategy", style="cyan")
        table.add_column("Lead")
        table.add_column("Architect")
        table.add_column("Engineer")
        table.add_column("QA")

        for name, agents in self.get_strategies().items():
            table.add_row(
                name,
                agents.get("lead", "-"),
                agents.get("architect", "-"),
                agents.get("engineer", "-"),
                agents.get("qa", "-"),
            )

        console.print(table)
