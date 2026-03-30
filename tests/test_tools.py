"""Tests for tool system."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cadre.tools.base import ToolRegistry
from cadre.tools.file_ops import (
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    GlobTool,
    create_file_tools,
)
from cadre.tools.git import create_git_tools
from cadre.tools.shell import ShellTool


def test_tool_schema():
    tool = FileReadTool()
    schema = tool.to_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "file_read"
    assert "path" in schema["function"]["parameters"]["properties"]


def test_tool_registry():
    registry = ToolRegistry()
    tool = FileReadTool()
    registry.register(tool)
    assert registry.get("file_read") is tool
    assert registry.get("nonexistent") is None
    assert len(registry.list_tools()) == 1


@pytest.mark.asyncio
async def test_file_read_tool():
    tool = FileReadTool()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line one\nline two\nline three\n")
        path = f.name

    result = await tool.execute({"path": path})
    assert "line one" in result
    assert "line two" in result
    Path(path).unlink()


@pytest.mark.asyncio
async def test_file_read_nonexistent():
    tool = FileReadTool()
    result = await tool.execute({"path": "/nonexistent/file.txt"})
    assert "Error" in result


@pytest.mark.asyncio
async def test_file_write_and_edit():
    write_tool = FileWriteTool()
    edit_tool = FileEditTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/test.txt"

        # Write
        result = await write_tool.execute({"path": path, "content": "hello world"})
        assert "Written" in result

        # Edit
        result = await edit_tool.execute(
            {
                "path": path,
                "old_string": "hello",
                "new_string": "goodbye",
            }
        )
        assert "Edited" in result
        assert Path(path).read_text() == "goodbye world"


@pytest.mark.asyncio
async def test_glob_tool():
    tool = GlobTool()
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").touch()
        (Path(tmpdir) / "test.sql").touch()
        result = await tool.execute({"pattern": "*.py", "path": tmpdir})
        assert "test.py" in result
        assert "test.sql" not in result


def test_shell_tool_deny():
    tool = ShellTool(deny_patterns=["rm -rf*"])
    allowed, _reason = tool._is_allowed("rm -rf /")
    assert not allowed


def test_shell_tool_allow():
    tool = ShellTool(allow_patterns=["git *"], deny_patterns=[])
    allowed, _ = tool._is_allowed("git status")
    assert allowed


def test_create_file_tools():
    tools = create_file_tools()
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert "file_read" in names
    assert "file_write" in names
    assert "glob" in names


def test_create_git_tools():
    tools = create_git_tools()
    assert len(tools) == 4
    names = {t.name for t in tools}
    assert "git_status" in names
    assert "git_commit" in names
