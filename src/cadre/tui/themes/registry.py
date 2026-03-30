"""Theme registry — loads built-in and custom .tcss themes."""

from __future__ import annotations

from pathlib import Path

THEMES_DIR = Path(__file__).parent

BUILTIN_THEMES: dict[str, Path] = {
    "dark": THEMES_DIR / "dark.tcss",
    "light": THEMES_DIR / "light.tcss",
    "monokai": THEMES_DIR / "monokai.tcss",
}


class ThemeRegistry:
    """Manages available themes (built-in + custom from .cadre/themes/)."""

    def __init__(self, project_path: Path | None = None) -> None:
        self.themes: dict[str, Path] = dict(BUILTIN_THEMES)
        # Load custom themes from .cadre/themes/
        if project_path:
            custom_dir = project_path / ".cadre" / "themes"
            if custom_dir.exists():
                for f in custom_dir.glob("*.tcss"):
                    self.themes[f.stem] = f

    def list_themes(self) -> list[str]:
        """Return available theme names."""
        return sorted(self.themes.keys())

    def get_css_path(self, name: str) -> Path:
        """Get the CSS file path for a theme. Falls back to dark."""
        return self.themes.get(name, BUILTIN_THEMES["dark"])
