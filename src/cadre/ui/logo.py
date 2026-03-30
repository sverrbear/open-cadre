"""ASCII logo for OpenCadre."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

LOGO = r"""
   ____                    ______          __
  / __ \____  ___  ____   / ____/___ _____/ /_____  ___
 / / / / __ \/ _ \/ __ \ / /   / __ `/ __  / ___/ / _ \
/ /_/ / /_/ /  __/ / / // /___/ /_/ / /_/ / /  /  __/
\____/ .___/\___/_/ /_/ \____/\__,_/\__,_/_/   \___/
    /_/
"""


def print_logo(console: Console, version: str = "") -> None:
    """Print the OpenCadre ASCII logo."""
    text = Text(LOGO.rstrip(), style="bold cyan")
    console.print(text)
    if version:
        console.print(f"  [dim]v{version} — Provider-agnostic AI team for data engineering[/dim]")
    console.print()
