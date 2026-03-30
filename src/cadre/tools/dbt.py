"""dbt operation tools."""

from __future__ import annotations

import asyncio
from typing import Any

from cadre.tools.base import Tool


class _DbtTool(Tool):
    """Base for dbt tools."""

    async def _run_dbt(self, *args: str) -> str:
        cmd = ["dbt", *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                return f"Error (exit {proc.returncode}):\n{err}\n{output}"
            return output or "(no output)"
        except FileNotFoundError:
            return "Error: dbt is not installed or not in PATH"
        except asyncio.TimeoutError:
            return "Error: dbt command timed out"
        except Exception as e:
            return f"Error: {e}"


class DbtCompileTool(_DbtTool):
    def __init__(self) -> None:
        super().__init__(
            name="dbt_compile",
            description="Compile a dbt model and return the compiled SQL.",
            parameters={
                "type": "object",
                "properties": {
                    "select": {
                        "type": "string",
                        "description": "Model selector (e.g. 'my_model' or '+my_model+')",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        cmd_args = ["compile"]
        if args.get("select"):
            cmd_args.extend(["--select", args["select"]])
        return await self._run_dbt(*cmd_args)


class DbtLsTool(_DbtTool):
    def __init__(self) -> None:
        super().__init__(
            name="dbt_ls",
            description="List dbt resources (models, tests, sources, etc.).",
            parameters={
                "type": "object",
                "properties": {
                    "select": {"type": "string", "description": "Resource selector"},
                    "resource_type": {
                        "type": "string",
                        "description": "Filter by type: model, test, source, seed, snapshot",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any]) -> str:
        cmd_args = ["ls"]
        if args.get("select"):
            cmd_args.extend(["--select", args["select"]])
        if args.get("resource_type"):
            cmd_args.extend(["--resource-type", args["resource_type"]])
        return await self._run_dbt(*cmd_args)


class DbtTestTool(_DbtTool):
    def __init__(self) -> None:
        super().__init__(
            name="dbt_test",
            description="Run dbt tests.",
            parameters={
                "type": "object",
                "properties": {
                    "select": {"type": "string", "description": "Test selector"},
                },
                "required": [],
            },
            dangerous=True,
        )

    async def execute(self, args: dict[str, Any]) -> str:
        cmd_args = ["test"]
        if args.get("select"):
            cmd_args.extend(["--select", args["select"]])
        return await self._run_dbt(*cmd_args)


def create_dbt_tools() -> list[Tool]:
    """Create all dbt tools."""
    return [DbtCompileTool(), DbtLsTool(), DbtTestTool()]
