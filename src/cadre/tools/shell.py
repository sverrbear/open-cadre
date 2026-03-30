"""Shell command execution tool with allowlist/denylist sandboxing."""

from __future__ import annotations

import asyncio
import fnmatch
from dataclasses import dataclass, field
from typing import Any

from cadre.tools.base import Tool


class ShellTool(Tool):
    """Execute shell commands with configurable allow/deny rules."""

    def __init__(
        self,
        allow_patterns: list[str] | None = None,
        deny_patterns: list[str] | None = None,
    ) -> None:
        super().__init__(
            name="shell",
            description="Execute a shell command and return its output. Commands are checked against allow/deny rules.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 120)",
                    },
                },
                "required": ["command"],
            },
            dangerous=True,
        )
        self.allow_patterns = allow_patterns or ["*"]
        self.deny_patterns = deny_patterns or [
            "rm -rf *",
            "DROP *",
            "DELETE FROM *",
            "TRUNCATE *",
        ]

    def _is_allowed(self, command: str) -> tuple[bool, str]:
        """Check if a command is allowed by the allow/deny rules."""
        # Check deny list first
        for pattern in self.deny_patterns:
            if fnmatch.fnmatch(command, pattern) or fnmatch.fnmatch(command.strip(), pattern):
                return False, f"Command denied by rule: {pattern}"

        # Check allow list
        for pattern in self.allow_patterns:
            if fnmatch.fnmatch(command, pattern) or fnmatch.fnmatch(command.strip(), pattern):
                return True, ""

        return False, "Command not in allow list"

    async def execute(self, args: dict[str, Any]) -> str:
        command = args["command"]
        timeout = args.get("timeout", 120)

        allowed, reason = self._is_allowed(command)
        if not allowed:
            return f"Error: {reason}"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                output_parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace')}")
            if proc.returncode != 0:
                output_parts.append(f"Exit code: {proc.returncode}")

            return "\n".join(output_parts) if output_parts else "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
