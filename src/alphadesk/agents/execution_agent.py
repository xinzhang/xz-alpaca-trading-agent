"""Execution Node: the last, hard-coded gate. Applies risk_rules.evaluate_order to each
ticker's proposed decision; only then submits a real (or DRY_RUN-simulated) order.
"""

from datetime import UTC, datetime

from alpaca.trading.enums import OrderSide

from alphadesk.agents.base import AgentNode
from alphadesk.clients.alpaca_client import AlpacaClient
from alphadesk.clients.redis_bus import EventBus
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.db.models import Decision, TradeFill
from alphadesk.risk_rules import evaluate_order
from alphadesk.state import PipelineState, RiskVerdict, TickerState


class ExecutionAgent(AgentNode):
    name = "execution"

    def __init__(
        self, db: Database, event_bus: EventBus, alpaca: AlpacaClient, settings: Settings
    ) -> None:
        super().__init__(db, event_bus)
        self._alpaca = alpaca
        self._settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        budget = state.risk_budget
        for ticker in state.tickers:
            ts = state.ticker_states[ticker]
            if ts.decision is None:
                continue

            verdict = evaluate_order(
                budget, ticker, state.positions, ts.decision, ts.decision.action
            )
            ts.risk_verdict = verdict

            order_id = None
            if verdict.approved and ts.decision.action != "HOLD":
                order_id = await self._submit(
                    ticker, ts.decision.action, verdict.approved_notional, verdict.approved_qty
                )
                ts.executed = True
                ts.order_id = order_id

            await self._persist(ticker, ts, verdict)
            await self._log(
                "execution decided",
                ticker=ticker,
                action=ts.decision.action,
                risk_approved=verdict.approved,
                risk_reason=verdict.reason,
                executed=ts.executed,
            )
        return state

    async def _submit(
        self, ticker: str, action: str, notional: float | None, qty: float | None
    ) -> str:
        side = OrderSide.BUY if action == "BUY" else OrderSide.SELL

        if self._settings.dry_run:
            order_id = f"DRY-{ticker}-{datetime.now(UTC).timestamp():.0f}"
        elif action == "BUY":
            order = self._alpaca.submit_market_order(ticker, side, notional=notional)
            order_id = str(order.id)
        else:
            order = self._alpaca.submit_market_order(ticker, side, qty=qty)
            order_id = str(order.id)

        async with self._db.session() as session:
            session.add(
                TradeFill(
                    ts=datetime.now(UTC),
                    ticker=ticker,
                    side=side.value,
                    qty=qty if action != "BUY" else None,
                    notional=notional if action == "BUY" else None,
                    order_id=order_id,
                    dry_run=self._settings.dry_run,
                )
            )
            await session.commit()
        return order_id

    async def _persist(self, ticker: str, ts: TickerState, verdict: RiskVerdict) -> None:
        async with self._db.session() as session:
            session.add(
                Decision(
                    ts=datetime.now(UTC),
                    ticker=ticker,
                    action=ts.decision.action,
                    confidence=ts.decision.confidence,
                    rationale=ts.decision.rationale,
                    risk_approved=verdict.approved,
                    risk_reason=verdict.reason,
                    executed=ts.executed,
                )
            )
            await session.commit()
