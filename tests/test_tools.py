from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from moguangclaw.tools.bash import BashTool
from moguangclaw.tools.file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from moguangclaw.tools.registry import ToolRegistry


def _run(coro):
    return asyncio.run(coro)


def test_bash_success(tmp_path: Path):
    tool = BashTool(workspace_root=tmp_path, timeout=5)
    result = _run(tool.execute({"command": "echo hello"}))

    assert result.success is True
    assert "hello" in result.output["stdout"]


def test_bash_timeout(tmp_path: Path):
    tool = BashTool(workspace_root=tmp_path, timeout=1)
    command = f'"{sys.executable}" -c "import time; time.sleep(2)"'
    result = _run(tool.execute({"command": command}))

    assert result.success is False
    assert "timed out" in (result.error or "")


def test_bash_deny_pattern(tmp_path: Path):
    tool = BashTool(workspace_root=tmp_path, timeout=5)
    result = _run(tool.execute({"command": "rm -rf /"}))

    assert result.success is False
    assert "blocked" in (result.error or "")


def test_file_tools_happy_path(tmp_path: Path):
    write_tool = WriteFileTool(workspace_root=tmp_path)
    read_tool = ReadFileTool(workspace_root=tmp_path)
    edit_tool = EditFileTool(workspace_root=tmp_path)
    list_tool = ListDirTool(workspace_root=tmp_path)

    write_res = _run(write_tool.execute({"path": "hello.py", "content": "print('hello')\n"}))
    assert write_res.success is True

    read_res = _run(read_tool.execute({"path": "hello.py"}))
    assert read_res.success is True
    assert "print('hello')" in read_res.output["content"]

    edit_res = _run(
        edit_tool.execute(
            {
                "path": "hello.py",
                "old_text": "hello",
                "new_text": "world",
            }
        )
    )
    assert edit_res.success is True

    read_res_2 = _run(read_tool.execute({"path": "hello.py"}))
    assert "world" in read_res_2.output["content"]

    list_res = _run(list_tool.execute({"path": "."}))
    assert list_res.success is True
    assert any(item["name"] == "hello.py" for item in list_res.output["entries"])


def test_file_tools_block_path_escape(tmp_path: Path):
    tool = ReadFileTool(workspace_root=tmp_path)
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    result = _run(tool.execute({"path": str(outside_file)}))
    assert result.success is False
    assert "outside sandbox" in (result.error or "")


def test_registry_schema_export(tmp_path: Path):
    registry = ToolRegistry()
    registry.register(WriteFileTool(workspace_root=tmp_path))
    registry.register(ReadFileTool(workspace_root=tmp_path))

    output_file = tmp_path / "TOOLS.md"
    registry.export_tools_markdown(output_file)

    assert output_file.exists()
    text = output_file.read_text(encoding="utf-8")
    assert "write_file" in text
    assert "read_file" in text
    assert len(registry.schemas()) == 2
