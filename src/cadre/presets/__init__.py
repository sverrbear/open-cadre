"""Agent presets — ready-made Claude Code agent team templates."""

from __future__ import annotations

from pathlib import Path

PRESETS_DIR = Path(__file__).parent

# Team compositions
TEAM_PRESETS: dict[str, list[str]] = {
    "full": ["lead", "engineer", "architect", "qa"],
    "solo": ["solo"],
    "dev": ["lead", "engineer"],
    "review": ["lead", "engineer", "qa"],
}


def list_presets() -> list[str]:
    """Return names of all available agent presets."""
    return [p.stem for p in PRESETS_DIR.glob("*.md")]


def load_preset(name: str) -> str:
    """Load a preset's markdown content by name."""
    path = PRESETS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Preset '{name}' not found")
    return path.read_text()


def list_team_presets() -> dict[str, list[str]]:
    """Return available team compositions."""
    return dict(TEAM_PRESETS)
