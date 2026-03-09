from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .base import BaseLLMProvider, LLMResponse, ToolCall, parse_json_arguments


class OpenAIProvider(BaseLLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        client: Any | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key, base_url=base_url, temperature=temperature, max_tokens=max_tokens)
        self.client = client or self._build_client()

    def _build_client(self) -> Any:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required to use OpenAIProvider") from exc

        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        stream_handler: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if stream:
            payload["stream"] = True
            return await self._chat_stream(payload, stream_handler)

        completion = await self.client.chat.completions.create(**payload)
        choice = completion.choices[0]
        message = choice.message
        tool_calls = []

        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                raw_args = tc.function.arguments or "{}"
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        raw_arguments=raw_args,
                        arguments=parse_json_arguments(raw_args),
                    )
                )

        return LLMResponse(
            content=_coerce_content(getattr(message, "content", "")),
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None),
            raw_response=completion,
        )

    async def _chat_stream(
        self,
        payload: dict[str, Any],
        stream_handler: Callable[[str], None] | None,
    ) -> LLMResponse:
        stream_resp = await self.client.chat.completions.create(**payload)

        content_parts: list[str] = []
        finish_reason: str | None = None
        tool_acc: dict[int, dict[str, str]] = defaultdict(lambda: {"id": "", "name": "", "arguments": ""})

        async for chunk in stream_resp:
            if not getattr(chunk, "choices", None):
                continue
            choice = chunk.choices[0]
            finish_reason = finish_reason or getattr(choice, "finish_reason", None)
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue

            delta_content = _coerce_content(getattr(delta, "content", ""))
            if delta_content:
                content_parts.append(delta_content)
                if stream_handler:
                    stream_handler(delta_content)

            for tool_delta in getattr(delta, "tool_calls", []) or []:
                idx = getattr(tool_delta, "index", 0) or 0
                entry = tool_acc[idx]
                if getattr(tool_delta, "id", None):
                    entry["id"] = tool_delta.id
                function = getattr(tool_delta, "function", None)
                if function is not None:
                    if getattr(function, "name", None):
                        entry["name"] = function.name
                    if getattr(function, "arguments", None):
                        entry["arguments"] += function.arguments

        tool_calls: list[ToolCall] = []
        for index in sorted(tool_acc.keys()):
            item = tool_acc[index]
            raw_args = item["arguments"] or "{}"
            tool_calls.append(
                ToolCall(
                    id=item["id"] or f"call_{index}",
                    name=item["name"],
                    raw_arguments=raw_args,
                    arguments=parse_json_arguments(raw_args),
                )
            )

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw_response=None,
        )


def _coerce_content(raw_content: Any) -> str:
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        chunks: list[str] = []
        for part in raw_content:
            text = ""
            if isinstance(part, dict):
                text = str(part.get("text", ""))
            else:
                text = str(getattr(part, "text", ""))
            if text:
                chunks.append(text)
        return "".join(chunks)
    return str(raw_content)
