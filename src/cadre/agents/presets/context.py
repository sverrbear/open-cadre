"""Shared helper for building agent context from config."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadre.config import CadreConfig


def build_extra_context(config: CadreConfig, agent_name: str) -> str:
    """Build extra context string from project context + agent-specific context."""
    parts = []
    context_block = config.get_context_block()
    if context_block:
        parts.append(context_block)
    agent_cfg = config.get_agent_config(agent_name)
    if agent_cfg.extra_context:
        parts.append(agent_cfg.extra_context)
    if not parts:
        return ""
    return "\n\n## Additional Context\n" + "\n\n".join(parts) + "\n"
