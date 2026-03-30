"""Codebase search tool — ripgrep-style search across files."""

from __future__ import annotations

import asyncio
from typing import Any

from cadre.tools.base import Tool


class CodeSearchTool(Tool):
    """Search codebase using ripgrep (rg) if available, falling back to grep."""

    def __init__(self) -> None:
        super().__init__(
            name="search",
            description=(
                "Search the codebase for a pattern. Uses ripgrep if available,"
                " falls back to grep. Returns matching lines with file paths and line numbers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (regex supported)"},
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "File type filter (e.g. 'py', 'sql', 'yml')",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case insensitive search",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        query = args["query"]
        path = args.get("path", ".")
        file_type = args.get("file_type")
        case_insensitive = args.get("case_insensitive", False)

        # Try ripgrep first
        cmd = await self._build_rg_cmd(query, path, file_type, case_insensitive)
        if cmd is None:
            # Fallback to grep
            cmd = self._build_grep_cmd(query, path, file_type, case_insensitive)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace").strip()

            if not output:
                return "No matches found"

            lines = output.splitlines()
            if len(lines) > 100:
                return "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more matches)"
            return output
        except asyncio.TimeoutError:
            return "Error: Search timed out"
        except Exception as e:
            return f"Error: {e}"

    async def _build_rg_cmd(
        self, query: str, path: str, file_type: str | None, case_insensitive: bool
    ) -> list[str] | None:
        """Build ripgrep command, returns None if rg is not available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rg",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                return None
        except FileNotFoundError:
            return None

        cmd = ["rg", "-n", "--no-heading"]
        if case_insensitive:
            cmd.append("-i")
        if file_type:
            cmd.extend(["--type", file_type])
        cmd.extend([query, path])
        return cmd

    def _build_grep_cmd(
        self, query: str, path: str, file_type: str | None, case_insensitive: bool
    ) -> list[str]:
        """Build grep command as fallback."""
        cmd = ["grep", "-rn", "-E"]
        if case_insensitive:
            cmd.append("-i")
        if file_type:
            cmd.append(f"--include=*.{file_type}")
        cmd.extend([query, path])
        return cmd
