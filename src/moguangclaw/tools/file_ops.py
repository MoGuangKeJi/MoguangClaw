from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolExecutionResult


class _SandboxedFileTool(BaseTool):
    def __init__(self, workspace_root: Path, allowed_paths: list[str] | None = None) -> None:
        self.workspace_root = workspace_root.expanduser().resolve()
        extra_roots = [Path(p).expanduser().resolve() for p in (allowed_paths or [])]
        self.allowed_roots = [self.workspace_root, *extra_roots]

    def _resolve_path(self, raw_path: str) -> Path:
        input_path = Path(raw_path).expanduser()
        if not input_path.is_absolute():
            input_path = self.workspace_root / input_path

        resolved = input_path.resolve()
        if not any(_is_relative_to(resolved, root) for root in self.allowed_roots):
            raise PermissionError(f"Path is outside sandbox: {resolved}")
        return resolved


class ReadFileTool(_SandboxedFileTool):
    name = "read_file"
    description = "Read file content with optional line range."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file"},
            "start_line": {"type": "integer", "minimum": 1},
            "end_line": {"type": "integer", "minimum": 1},
        },
        "required": ["path"],
    }

    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = self._resolve_path(str(arguments["path"]))
            if not path.exists():
                return ToolExecutionResult(success=False, error=f"File not found: {path}")
            if path.is_dir():
                return ToolExecutionResult(success=False, error=f"Path is a directory: {path}")

            text = path.read_text(encoding="utf-8", errors="replace")
            start_line = arguments.get("start_line")
            end_line = arguments.get("end_line")
            if start_line or end_line:
                lines = text.splitlines()
                start_idx = int(start_line or 1) - 1
                end_idx = int(end_line or len(lines))
                text = "\n".join(lines[start_idx:end_idx])

            return ToolExecutionResult(success=True, output={"path": str(path), "content": text})
        except PermissionError as exc:
            return ToolExecutionResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(success=False, error=str(exc))


class WriteFileTool(_SandboxedFileTool):
    name = "write_file"
    description = "Create or overwrite file content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file"},
            "content": {"type": "string", "description": "Content to write"},
            "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
        },
        "required": ["path", "content"],
    }

    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = self._resolve_path(str(arguments["path"]))
            content = str(arguments.get("content", ""))
            append_mode = bool(arguments.get("append", False))

            path.parent.mkdir(parents=True, exist_ok=True)
            if append_mode:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(content)
            else:
                path.write_text(content, encoding="utf-8")

            return ToolExecutionResult(
                success=True,
                output={"path": str(path), "bytes_written": len(content.encode("utf-8")), "append": append_mode},
            )
        except PermissionError as exc:
            return ToolExecutionResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(success=False, error=str(exc))


class EditFileTool(_SandboxedFileTool):
    name = "edit_file"
    description = "Find and replace text in a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to file"},
            "old_text": {"type": "string", "description": "Text to replace"},
            "new_text": {"type": "string", "description": "Replacement text"},
            "replace_all": {"type": "boolean", "default": False},
        },
        "required": ["path", "old_text", "new_text"],
    }

    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        try:
            path = self._resolve_path(str(arguments["path"]))
            old_text = str(arguments["old_text"])
            new_text = str(arguments["new_text"])
            replace_all = bool(arguments.get("replace_all", False))

            if not path.exists():
                return ToolExecutionResult(success=False, error=f"File not found: {path}")
            if path.is_dir():
                return ToolExecutionResult(success=False, error=f"Path is a directory: {path}")

            original = path.read_text(encoding="utf-8", errors="replace")
            if old_text not in original:
                return ToolExecutionResult(success=False, error="old_text not found in file")

            if replace_all:
                updated = original.replace(old_text, new_text)
                replacements = original.count(old_text)
            else:
                updated = original.replace(old_text, new_text, 1)
                replacements = 1

            path.write_text(updated, encoding="utf-8")
            return ToolExecutionResult(
                success=True,
                output={"path": str(path), "replacements": replacements, "replace_all": replace_all},
            )
        except PermissionError as exc:
            return ToolExecutionResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(success=False, error=str(exc))


class ListDirTool(_SandboxedFileTool):
    name = "list_dir"
    description = "List directory entries under sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path", "default": "."},
            "include_hidden": {"type": "boolean", "default": False},
        },
        "required": [],
    }

    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        raw_path = str(arguments.get("path", "."))
        include_hidden = bool(arguments.get("include_hidden", False))

        try:
            path = self._resolve_path(raw_path)
            if not path.exists():
                return ToolExecutionResult(success=False, error=f"Directory not found: {path}")
            if not path.is_dir():
                return ToolExecutionResult(success=False, error=f"Path is not directory: {path}")

            entries = []
            for item in sorted(path.iterdir(), key=lambda p: p.name):
                if not include_hidden and item.name.startswith("."):
                    continue
                entry_type = "dir" if item.is_dir() else "file"
                size = item.stat().st_size if item.is_file() else None
                entries.append({"name": item.name, "type": entry_type, "size": size})

            return ToolExecutionResult(success=True, output={"path": str(path), "entries": entries})
        except PermissionError as exc:
            return ToolExecutionResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(success=False, error=str(exc))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
