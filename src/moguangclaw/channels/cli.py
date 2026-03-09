from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.prompt import Prompt

from .base import BaseChannel, IncomingMessage


@dataclass(slots=True)
class CLIChannel(BaseChannel):
    session_id: str = "cli-default"
    sender_id: str = "cli-user"
    stream: bool = True
    console: Console = field(default_factory=Console)

    async def run(self, agent_runner: Any) -> None:
        self.console.print("[bold cyan]MoguangClaw CLI[/bold cyan] 已启动，输入 `exit` 结束。")

        while True:
            try:
                user_input = Prompt.ask("[bold blue]You[/bold blue]").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[bold yellow]会话结束[/bold yellow]")
                return

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                self.console.print("[bold yellow]会话结束[/bold yellow]")
                return

            incoming = IncomingMessage(
                channel="cli",
                sender_id=self.sender_id,
                session_id=self.session_id,
                content=user_input,
                timestamp=datetime.now(),
            )

            streamed = False

            def on_stream(token: str) -> None:
                nonlocal streamed
                if not self.stream:
                    return
                if not streamed:
                    self.console.print("[bold green]Assistant[/bold green]", end=": ")
                    streamed = True
                self.console.print(token, end="")

            outgoing = await agent_runner.handle_message(
                incoming,
                stream_handler=on_stream if self.stream else None,
            )

            if streamed:
                self.console.print()
            else:
                self.console.print(f"[bold green]Assistant[/bold green]: {outgoing.content}")
