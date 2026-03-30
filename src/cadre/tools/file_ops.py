"""File operation tools — read, write, edit, glob, grep."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cadre.tools.base import Tool


class FileReadTool(Tool):
    """Read file contents."""

    def __init__(self) -> None:
        super().__init__(
            name="file_read",
            description="Read the contents of a file. Returns the file content as a string.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read"},
                    "offset": {
                        "type": "integer",
                        "description": "Line number to start reading from (0-indexed)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        path = Path(args["path"]).resolve()
        if not path.exists():
            return f"Error: File not found: {path}"
        if not path.is_file():
            return f"Error: Not a file: {path}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines(keepends=True)
            offset = args.get("offset", 0)
            limit = args.get("limit")
            lines = lines[offset : offset + limit] if limit is not None else lines[offset:]
            numbered = [f"{i + offset + 1}\t{line}" for i, line in enumerate(lines)]
            return "".join(numbered)
        except Exception as e:
            return f"Error reading file: {e}"


class FileWriteTool(Tool):
    """Write content to a file."""

    def __init__(self) -> None:
        super().__init__(
            name="file_write",
            description=(
                "Write content to a file. Creates the file if it doesn't exist,"
                " overwrites if it does."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Content to write to the file"},
                },
                "required": ["path", "content"],
            },
            dangerous=True,
        )

    async def execute(self, args: dict[str, Any]) -> str:
        path = Path(args["path"]).resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return f"Written {len(args['content'])} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class FileEditTool(Tool):
    """Edit a file by replacing text."""

    def __init__(self) -> None:
        super().__init__(
            name="file_edit",
            description="Edit a file by replacing an exact string match with new content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to edit"},
                    "old_string": {
                        "type": "string",
                        "description": "Exact string to find and replace",
                    },
                    "new_string": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
            dangerous=True,
        )

    async def execute(self, args: dict[str, Any]) -> str:
        path = Path(args["path"]).resolve()
        if not path.exists():
            return f"Error: File not found: {path}"
        try:
            content = path.read_text(encoding="utf-8")
            old = args["old_string"]
            if old not in content:
                return "Error: old_string not found in file"
            if content.count(old) > 1:
                return "Error: old_string matches multiple locations — provide more context"
            new_content = content.replace(old, args["new_string"], 1)
            path.write_text(new_content, encoding="utf-8")
            return f"Edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    def __init__(self) -> None:
        super().__init__(
            name="glob",
            description="Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.sql').",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern to match"},
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)",
                    },
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        base = Path(args.get("path", ".")).resolve()
        pattern = args["pattern"]
        try:
            matches = sorted(base.glob(pattern))
            if not matches:
                return "No files matched"
            return "\n".join(str(m.relative_to(base)) for m in matches[:200])
        except Exception as e:
            return f"Error: {e}"


class GrepTool(Tool):
    """Search file contents for a pattern."""

    def __init__(self) -> None:
        super().__init__(
            name="grep",
            description=(
                "Search for a regex pattern in files."
                " Returns matching lines with file paths and line numbers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in",
                    },
                    "glob": {
                        "type": "string",
                        "description": "File glob to filter (e.g. '*.py')",
                    },
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        import subprocess

        pattern = args["pattern"]
        path = args.get("path", ".")
        file_glob = args.get("glob")

        cmd = ["grep", "-rn", "-E", pattern, path]
        if file_glob:
            cmd = ["grep", "-rn", "-E", f"--include={file_glob}", pattern, path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout.strip()
            if not output:
                return "No matches found"
            lines = output.splitlines()
            if len(lines) > 100:
                return "\n".join(lines[:100]) + f"\n... ({len(lines) - 100} more matches)"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Search timed out"
        except Exception as e:
            return f"Error: {e}"


def create_file_tools() -> list[Tool]:
    """Create all file operation tools."""
    return [FileReadTool(), FileWriteTool(), FileEditTool(), GlobTool(), GrepTool()]
