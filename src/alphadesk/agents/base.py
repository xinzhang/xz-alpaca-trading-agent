"""Base class every pipeline node extends: uniform logging + live-event publishing."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from alphadesk.clients.protocols import EventPublisher
from alphadesk.db.base import Database
from alphadesk.db.models import AgentLogEntry
from alphadesk.state import PipelineState


class AgentNode(ABC):
    name: str

    def __init__(self, db: Database, event_bus: EventPublisher) -> None:
        self._db = db
        self._event_bus = event_bus

    @abstractmethod
    async def run(self, state: PipelineState) -> PipelineState: ...

    async def _log(self, message: str, ticker: str | None = None, **payload: Any) -> None:
        ts = datetime.now(UTC)
        async with self._db.session() as session:
            session.add(
                AgentLogEntry(
                    ts=ts, node=self.name, ticker=ticker, message=message, payload=payload
                )
            )
            await session.commit()
        await self._event_bus.publish(
            "agent_log",
            {"ts": ts, "node": self.name, "ticker": ticker, "message": message, **payload},
        )
