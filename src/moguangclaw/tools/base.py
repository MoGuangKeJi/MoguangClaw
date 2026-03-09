from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
import json
from typing import Any, ClassVar


TOOL_CLASS_REGISTRY: dict[str, type["BaseTool"]] = {}


@dataclass(slots=True)
class ToolExecutionResult:
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message_content(self) -> str:
        payload = {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }
        return json.dumps(payload, ensure_ascii=False)


class BaseTool(ABC):
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            TOOL_CLASS_REGISTRY[cls.name] = cls

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> ToolExecutionResult:
        context = context or {}
        if asyncio.iscoroutinefunction(self.run):
            return await self.run(arguments, context)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, arguments, context)

    @abstractmethod
    def run(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolExecutionResult:
        raise NotImplementedError
