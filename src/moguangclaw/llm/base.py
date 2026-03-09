from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any, Callable


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str | None = None

    def as_assistant_tool_call(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.raw_arguments if self.raw_arguments is not None else json.dumps(self.arguments, ensure_ascii=False),
            },
        }


@dataclass(slots=True)
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class BaseLLMProvider(ABC):
    def __init__(self, model: str, api_key: str, base_url: str, temperature: float = 0.2, max_tokens: int = 4000) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        stream_handler: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError


def parse_json_arguments(raw_arguments: str | None) -> dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {"_raw": raw_arguments}
    return parsed if isinstance(parsed, dict) else {"_value": parsed}
