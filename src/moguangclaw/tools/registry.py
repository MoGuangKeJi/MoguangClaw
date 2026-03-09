from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import AppConfig
from .base import BaseTool, ToolExecutionResult
from .bash import BashTool
from .file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> ToolExecutionResult:
        tool = self.get(name)
        return await tool.execute(arguments, context)

    def export_tools_markdown(self, output_path: Path) -> None:
        lines: list[str] = ["# TOOLS", ""]
        for tool in self.all_tools():
            lines.append(f"## {tool.name}")
            lines.append("")
            lines.append(tool.description)
            lines.append("")
            lines.append("参数 Schema:")
            lines.append("```json")
            lines.append(_pretty_json(tool.parameters))
            lines.append("```")
            lines.append("")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def build_default_registry(config: AppConfig) -> ToolRegistry:
    registry = ToolRegistry()
    workspace_root = config.workspace_root

    registry.register(
        BashTool(
            workspace_root=workspace_root,
            timeout=config.tools.bash.timeout,
            deny_patterns=config.tools.bash.deny_patterns,
        )
    )
    registry.register(
        ReadFileTool(
            workspace_root=workspace_root,
            allowed_paths=config.tools.file.allowed_paths,
        )
    )
    registry.register(
        WriteFileTool(
            workspace_root=workspace_root,
            allowed_paths=config.tools.file.allowed_paths,
        )
    )
    registry.register(
        EditFileTool(
            workspace_root=workspace_root,
            allowed_paths=config.tools.file.allowed_paths,
        )
    )
    registry.register(
        ListDirTool(
            workspace_root=workspace_root,
            allowed_paths=config.tools.file.allowed_paths,
        )
    )

    return registry


def _pretty_json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, indent=2, ensure_ascii=False)
