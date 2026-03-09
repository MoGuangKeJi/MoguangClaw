from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class IncomingMessage:
    channel: str
    sender_id: str
    session_id: str
    content: str
    attachments: list[Any] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class OutgoingMessage:
    channel: str
    session_id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class BaseChannel(ABC):
    @abstractmethod
    async def run(self, agent_runner: Any) -> None:
        raise NotImplementedError
