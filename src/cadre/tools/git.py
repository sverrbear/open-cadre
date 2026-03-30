"""Git operation tools."""

from __future__ import annotations

import asyncio
from typing import Any

from cadre.tools.base import Tool


class _GitTool(Tool):
    """Base for git tools — runs git commands."""

    async def _run_git(self, *args: str, cwd: str | None = None) -> str:
        cmd = ["git", *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                return f"Error (exit {proc.returncode}): {err}"
            return output or "(no output)"
        except asyncio.TimeoutError:
            return "Error: git command timed out"
        except Exception as e:
            return f"Error: {e}"


class GitStatusTool(_GitTool):
    def __init__(self) -> None:
        super().__init__(
            name="git_status",
            description="Show the working tree status (staged, unstaged, untracked files).",
            parameters={"type": "object", "properties": {}, "required": []},
        )

    async def execute(self, args: dict[str, Any]) -> str:
        return await self._run_git("status")


class GitDiffTool(_GitTool):
    def __init__(self) -> None:
        super().__init__(
            name="git_diff",
            description="Show changes between commits, commit and working tree, etc.",
            parameters={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes (--cached)",
                    },
                    "ref": {
                        "type": "string",
                        "description": "Compare against a specific ref (branch, commit, tag)",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        cmd_args = ["diff"]
        if args.get("staged"):
            cmd_args.append("--cached")
        if args.get("ref"):
            cmd_args.append(args["ref"])
        return await self._run_git(*cmd_args)


class GitCommitTool(_GitTool):
    def __init__(self) -> None:
        super().__init__(
            name="git_commit",
            description="Stage files and create a commit.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to stage (defaults to all modified)",
                    },
                },
                "required": ["message"],
            },
            dangerous=True,
        )

    async def execute(self, args: dict[str, Any]) -> str:
        files = args.get("files", ["."])
        for f in files:
            await self._run_git("add", f)
        return await self._run_git("commit", "-m", args["message"])


class GitLogTool(_GitTool):
    def __init__(self) -> None:
        super().__init__(
            name="git_log",
            description="Show recent commit history.",
            parameters={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of commits to show (default: 10)",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        count = str(args.get("count", 10))
        return await self._run_git("log", f"-{count}", "--oneline")


def create_git_tools() -> list[Tool]:
    """Create all git tools."""
    return [GitStatusTool(), GitDiffTool(), GitCommitTool(), GitLogTool()]
