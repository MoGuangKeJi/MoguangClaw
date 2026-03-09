from __future__ import annotations

from typing import Any

from .store import apply_sliding_window


def build_context_messages(
    system_prompt: str,
    memory_text: str,
    log_text: str,
    history: list[dict[str, Any]],
    user_message: str,
    max_history_turns: int,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if memory_text:
        messages.append({"role": "system", "content": f"# LONG_TERM_MEMORY\n\n{memory_text}"})
    if log_text:
        messages.append({"role": "system", "content": f"# RECENT_LOGS\n\n{log_text}"})

    messages.extend(apply_sliding_window(history, max_history_turns))
    messages.append({"role": "user", "content": user_message})
    return messages
