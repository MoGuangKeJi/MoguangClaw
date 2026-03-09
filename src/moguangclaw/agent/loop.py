from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..llm.base import BaseLLMProvider, ToolCall
from ..memory.store import SessionStore
from ..tools.registry import ToolRegistry
from .context import ContextBuilder


@dataclass(slots=True)
class AgentResult:
    content: str
    tool_invocations: int
    reached_max_turns: bool = False


class AgentLoop:
    def __init__(
        self,
        provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        session_store: SessionStore,
        context_builder: ContextBuilder,
        max_turns: int = 20,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.session_store = session_store
        self.context_builder = context_builder
        self.max_turns = max_turns

    async def run(
        self,
        session_id: str,
        user_message: str,
        stream_handler: Callable[[str], None] | None = None,
    ) -> AgentResult:
        history = self.session_store.load_messages(session_id)
        messages = self.context_builder.build_messages(history, user_message)

        persisted_messages: list[dict[str, object]] = [{"role": "user", "content": user_message}]
        tool_invocations = 0

        for _ in range(self.max_turns):
            llm_response = await self.provider.chat(
                messages=messages,
                tools=self.tool_registry.schemas(),
                stream=True if stream_handler else False,
                stream_handler=stream_handler,
            )

            assistant_message = {"role": "assistant", "content": llm_response.content}
            if llm_response.tool_calls:
                assistant_message["tool_calls"] = [tool_call.as_assistant_tool_call() for tool_call in llm_response.tool_calls]

            messages.append(assistant_message)
            persisted_messages.append(assistant_message)

            if not llm_response.tool_calls:
                self.session_store.append_messages(session_id, persisted_messages)
                return AgentResult(content=llm_response.content, tool_invocations=tool_invocations)

            for tool_call in llm_response.tool_calls:
                result_content = await self._execute_tool(session_id=session_id, tool_call=tool_call)
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": result_content,
                }
                messages.append(tool_message)
                persisted_messages.append(tool_message)
                tool_invocations += 1

        max_turn_notice = "已达到最大推理轮次，任务提前终止。"
        persisted_messages.append({"role": "assistant", "content": max_turn_notice})
        self.session_store.append_messages(session_id, persisted_messages)
        return AgentResult(content=max_turn_notice, tool_invocations=tool_invocations, reached_max_turns=True)

    async def _execute_tool(self, session_id: str, tool_call: ToolCall) -> str:
        try:
            result = await self.tool_registry.execute(
                tool_call.name,
                tool_call.arguments,
                context={"session_id": session_id},
            )
        except Exception as exc:  # noqa: BLE001
            return f'{{"success": false, "error": "{str(exc)}"}}'

        return result.to_message_content()
