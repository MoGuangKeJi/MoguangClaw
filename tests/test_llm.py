from __future__ import annotations

import asyncio
from types import SimpleNamespace

from moguangclaw.llm.openai_provider import OpenAIProvider
from moguangclaw.llm.qianwen import QianwenProvider


class _FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def _run(coro):
    return asyncio.run(coro)


def test_openai_provider_parses_tool_calls_non_stream():
    message = SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="write_file", arguments='{"path":"hello.py","content":"print(1)"}'),
            )
        ],
    )
    response = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="tool_calls")])
    client = _FakeClient(response)

    provider = OpenAIProvider(
        model="gpt-test",
        api_key="k",
        base_url="http://fake",
        client=client,
    )

    result = _run(
        provider.chat(
            messages=[{"role": "user", "content": "create file"}],
            tools=[{"type": "function", "function": {"name": "write_file"}}],
        )
    )

    assert result.content == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "write_file"
    assert result.tool_calls[0].arguments["path"] == "hello.py"
    payload = client.chat.completions.calls[0]
    assert payload["model"] == "gpt-test"
    assert payload["tool_choice"] == "auto"


def test_openai_provider_stream_collects_text_and_tools():
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="hel", tool_calls=[]),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="lo", tool_calls=[]),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="",
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_9",
                                function=SimpleNamespace(name="bash", arguments='{"command":"echo hi"}'),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ]
        ),
    ]

    stream = _FakeStream(chunks)
    client = _FakeClient(stream)
    provider = OpenAIProvider(
        model="gpt-test",
        api_key="k",
        base_url="http://fake",
        client=client,
    )

    streamed_tokens: list[str] = []
    result = _run(
        provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            tools=[{"type": "function", "function": {"name": "bash"}}],
            stream=True,
            stream_handler=streamed_tokens.append,
        )
    )

    assert result.content == "hello"
    assert streamed_tokens == ["hel", "lo"]
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "bash"
    assert result.tool_calls[0].arguments["command"] == "echo hi"


def test_qianwen_provider_is_openai_compatible():
    provider = QianwenProvider(
        model="qwen-test",
        api_key="k",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        client=_FakeClient(SimpleNamespace(choices=[])),
    )

    assert provider.model == "qwen-test"
    assert "dashscope" in provider.base_url
