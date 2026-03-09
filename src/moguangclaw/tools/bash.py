from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from .base import BaseTool, ToolExecutionResult


_DEFAULT_DENY_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=",
    r"shutdown",
    r"reboot",
    r"curl\s+[^|]*\|\s*(sh|bash)",
    r"wget\s+[^|]*\|\s*(sh|bash)",
    r"chmod\s+777",
    r"chown\s+root",
]


class BashTool(BaseTool):
    name = "bash"
    description = "Execute a shell command in the workspace root and return stdout/stderr."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Execution timeout in seconds", "minimum": 1},
        },
        "required": ["command"],
    }

    def __init__(self, workspace_root: Path, timeout: int = 30, deny_patterns: list[str] | None = None) -> None:
        self.workspace_root = workspace_root
        self.default_timeout = timeout
        raw_patterns = list(deny_patterns or [])
        if not raw_patterns:
            raw_patterns = list(_DEFAULT_DENY_PATTERNS)
        self._deny_regexes = [re.compile(pattern, flags=re.IGNORECASE) for pattern in raw_patterns]

    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        command = str(arguments.get("command", "")).strip()
        if not command:
            return ToolExecutionResult(success=False, error="command is required")

        if self._is_denied(command):
            return ToolExecutionResult(success=False, error="command blocked by deny patterns")

        timeout = int(arguments.get("timeout") or self.default_timeout)
        started_at = time.monotonic()

        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = round(time.monotonic() - started_at, 3)
            return ToolExecutionResult(
                success=False,
                error=f"command timed out after {timeout}s",
                metadata={"duration_seconds": elapsed, "timeout": timeout, "command": command},
            )

        elapsed = round(time.monotonic() - started_at, 3)
        success = completed.returncode == 0
        return ToolExecutionResult(
            success=success,
            output={
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "return_code": completed.returncode,
            },
            error=None if success else "command exited with non-zero status",
            metadata={"duration_seconds": elapsed, "timeout": timeout, "command": command},
        )

    def _is_denied(self, command: str) -> bool:
        return any(regex.search(command) for regex in self._deny_regexes)
