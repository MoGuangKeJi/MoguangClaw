from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionStore:
    sessions_dir: Path
    max_history_turns: int = 12

    def __post_init__(self) -> None:
        self.sessions_dir = self.sessions_dir.expanduser().resolve()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def session_file(self, session_id: str) -> Path:
        safe_id = session_id.replace("/", "_")
        return self.sessions_dir / f"{safe_id}.jsonl"

    def load_messages(self, session_id: str) -> list[dict[str, Any]]:
        path = self.session_file(session_id)
        if not path.exists():
            return []

        messages: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    messages.append(payload)
        return messages

    def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        self.append_messages(session_id, [message])

    def append_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        path = self.session_file(session_id)
        with path.open("a", encoding="utf-8") as handle:
            for message in messages:
                handle.write(json.dumps(message, ensure_ascii=False) + "\n")

    def trim_sliding_window(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return apply_sliding_window(messages, self.max_history_turns)


def apply_sliding_window(messages: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
    if max_turns <= 0:
        return messages

    user_indices = [idx for idx, message in enumerate(messages) if message.get("role") == "user"]
    if len(user_indices) <= max_turns:
        return messages

    start_index = user_indices[-max_turns]
    return messages[start_index:]
