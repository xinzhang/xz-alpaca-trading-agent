"""Signal Node ("the Quant"): technical analysis per ticker from Alpaca OHLCV bars."""

from alphadesk.agents.base import AgentNode
from alphadesk.clients.broker_protocol import Broker
from alphadesk.clients.protocols import EventPublisher
from alphadesk.db.base import Database
from alphadesk.indicators import TechnicalSnapshot, compute_snapshot
from alphadesk.state import PipelineState


class SignalAgent(AgentNode):
    name = "signal"

    def __init__(self, db: Database, event_bus: EventPublisher, alpaca: Broker) -> None:
        super().__init__(db, event_bus)
        self._alpaca = alpaca

    def compute(self, ticker: str) -> tuple[TechnicalSnapshot | None, int]:
        """Side-effect-free: (snapshot, bar count), or (None, 0) when no bars came back."""
        bars = self._alpaca.get_recent_bars(ticker)
        if bars.empty:
            return None, 0
        return compute_snapshot(bars), len(bars)

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            snapshot, _ = self.compute(ticker)
            if snapshot is None:
                await self._log("no bars returned, skipping ticker", ticker=ticker)
                continue
            state.ticker_states[ticker].technical = snapshot
            await self._log(
                "computed technical snapshot",
                ticker=ticker,
                last_price=snapshot.last_price,
                rsi_14=snapshot.rsi_14,
            )
        return state
