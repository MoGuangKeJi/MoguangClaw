from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..memory.context_builder import build_context_messages


@dataclass(slots=True)
class ContextBuilder:
    workspace_root: Path
    max_history_turns: int = 12

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.expanduser().resolve()

    def build_messages(self, history: list[dict[str, Any]], user_message: str) -> list[dict[str, Any]]:
        return build_context_messages(
            system_prompt=self.system_prompt(),
            memory_text=self.long_term_memory_text(),
            log_text=self.recent_logs_text(),
            history=history,
            user_message=user_message,
            max_history_turns=self.max_history_turns,
        )

    def system_prompt(self) -> str:
        sections = []
        soul = self._read_workspace_file("SOUL.md")
        agents = self._read_workspace_file("AGENTS.md")
        tools = self._read_workspace_file("TOOLS.md")

        if soul:
            sections.append(f"# SOUL\n\n{soul}")
        if agents:
            sections.append(f"# AGENTS\n\n{agents}")
        if tools:
            sections.append(f"# TOOLS\n\n{tools}")

        return "\n\n".join(sections)

    def long_term_memory_text(self) -> str:
        return self._read_workspace_file("MEMORY.md")

    def recent_logs_text(self) -> str:
        today = date.today()
        yesterday = today - timedelta(days=1)
        parts: list[str] = []
        for day in (yesterday, today):
            file_path = self.workspace_root / "memory" / f"{day.isoformat()}.md"
            if file_path.exists():
                text = file_path.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    parts.append(f"## {day.isoformat()}\n{text}")

        return "\n\n".join(parts)

    def _read_workspace_file(self, filename: str) -> str:
        path = self.workspace_root / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace").strip()
