"""Signal Node ("the Quant"): technical analysis per ticker from Alpaca OHLCV bars."""

from alphadesk.agents.base import AgentNode
from alphadesk.clients.broker_protocol import Broker
from alphadesk.clients.protocols import EventPublisher
from alphadesk.db.base import Database
from alphadesk.indicators import compute_snapshot
from alphadesk.state import PipelineState


class SignalAgent(AgentNode):
    name = "signal"

    def __init__(self, db: Database, event_bus: EventPublisher, alpaca: Broker) -> None:
        super().__init__(db, event_bus)
        self._alpaca = alpaca

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            bars = self._alpaca.get_recent_bars(ticker)
            if bars.empty:
                await self._log("no bars returned, skipping ticker", ticker=ticker)
                continue
            snapshot = compute_snapshot(bars)
            state.ticker_states[ticker].technical = snapshot
            await self._log(
                "computed technical snapshot",
                ticker=ticker,
                last_price=snapshot.last_price,
                rsi_14=snapshot.rsi_14,
            )
        return state
