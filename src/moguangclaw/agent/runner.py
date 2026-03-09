from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from ..channels.base import IncomingMessage, OutgoingMessage
from .loop import AgentLoop


@dataclass(slots=True)
class AgentRunner:
    loop: AgentLoop

    async def handle_message(
        self,
        incoming: IncomingMessage,
        stream_handler: Callable[[str], None] | None = None,
    ) -> OutgoingMessage:
        result = await self.loop.run(
            session_id=incoming.session_id,
            user_message=incoming.content,
            stream_handler=stream_handler,
        )

        return OutgoingMessage(
            channel=incoming.channel,
            session_id=incoming.session_id,
            content=result.content,
            timestamp=datetime.now(),
        )
