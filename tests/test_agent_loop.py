from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from moguangclaw.agent.context import ContextBuilder
from moguangclaw.agent.loop import AgentLoop
from moguangclaw.llm.base import BaseLLMProvider, LLMResponse, ToolCall
from moguangclaw.memory.store import SessionStore
from moguangclaw.tools.registry import ToolRegistry
from moguangclaw.tools.bash import BashTool
from moguangclaw.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool


class _FakeProvider(BaseLLMProvider):
    def __init__(self, responses: list[LLMResponse]) -> None:
        super().__init__(model="fake", api_key="", base_url="")
        self._responses = responses

    async def chat(self, messages, tools=None, stream=False, stream_handler=None):
        response = self._responses.pop(0)
        if stream and response.content and stream_handler:
            stream_handler(response.content)
        return response


def _run(coro):
    return asyncio.run(coro)


def test_agent_loop_can_execute_write_and_bash(tmp_path: Path):
    (tmp_path / "SOUL.md").write_text("soul", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("agents", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("memory", encoding="utf-8")
    (tmp_path / "memory").mkdir(exist_ok=True)

    registry = ToolRegistry()
    registry.register(BashTool(workspace_root=tmp_path, timeout=5))
    registry.register(ReadFileTool(workspace_root=tmp_path))
    registry.register(WriteFileTool(workspace_root=tmp_path))
    registry.register(EditFileTool(workspace_root=tmp_path))
    registry.register(ListDirTool(workspace_root=tmp_path))

    script_content = "print('hello world')\n"
    command = f'"{sys.executable}" hello.py'

    responses = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_write",
                    name="write_file",
                    arguments={"path": "hello.py", "content": script_content},
                )
            ],
        ),
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_bash",
                    name="bash",
                    arguments={"command": command},
                )
            ],
        ),
        LLMResponse(content="任务完成，脚本已执行。"),
    ]

    provider = _FakeProvider(responses)
    store = SessionStore(sessions_dir=tmp_path / "sessions", max_history_turns=12)
    context = ContextBuilder(workspace_root=tmp_path, max_history_turns=12)

    loop = AgentLoop(
        provider=provider,
        tool_registry=registry,
        session_store=store,
        context_builder=context,
        max_turns=10,
    )

    result = _run(loop.run(session_id="test", user_message="创建并运行 hello.py"))
    assert result.content == "任务完成，脚本已执行。"
    assert (tmp_path / "hello.py").exists()

    session_messages = store.load_messages("test")
    tool_messages = [item for item in session_messages if item.get("role") == "tool"]
    assert len(tool_messages) == 2
    bash_payload = json.loads(tool_messages[1]["content"])
    assert bash_payload["success"] is True
    assert "hello world" in bash_payload["output"]["stdout"]
