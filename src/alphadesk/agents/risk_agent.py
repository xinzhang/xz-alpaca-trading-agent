"""Risk Node ("the Bouncer"): reads real account state and computes this cycle's budget.

Enforcement of the budget against individual orders happens in ExecutionAgent — this
node's job is only to observe reality (buying power, positions, drawdown) and compute
hard-coded limits, independent of anything the LLM says.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from alphadesk.agents.base import AgentNode
from alphadesk.clients.broker_protocol import Broker
from alphadesk.clients.protocols import EventPublisher
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.db.models import PortfolioSnapshot
from alphadesk.risk_rules import compute_risk_budget
from alphadesk.state import PipelineState


class RiskAgent(AgentNode):
    name = "risk"

    def __init__(
        self, db: Database, event_bus: EventPublisher, alpaca: Broker, settings: Settings
    ) -> None:
        super().__init__(db, event_bus)
        self._alpaca = alpaca
        self._settings = settings

    async def _last_peak_equity(self, fallback: float) -> float:
        async with self._db.session() as session:
            result = await session.execute(select(PortfolioSnapshot.peak_equity).order_by(
                PortfolioSnapshot.ts.desc()
            ).limit(1))
            row = result.scalar_one_or_none()
            return row if row is not None else fallback

    async def run(self, state: PipelineState) -> PipelineState:
        account = self._alpaca.get_account()
        positions = self._alpaca.get_positions()
        state.positions = positions

        prior_peak = await self._last_peak_equity(fallback=account.equity)
        budget = compute_risk_budget(account, positions, prior_peak, self._settings)
        state.risk_budget = budget

        async with self._db.session() as session:
            session.add(
                PortfolioSnapshot(
                    ts=datetime.now(UTC),
                    equity=account.equity,
                    cash=account.cash,
                    buying_power=account.buying_power,
                    portfolio_value=account.portfolio_value,
                    peak_equity=budget.peak_equity,
                    drawdown_pct=budget.drawdown_pct,
                )
            )
            await session.commit()

        await self._log(
            "computed risk budget",
            equity=account.equity,
            drawdown_pct=budget.drawdown_pct,
            trading_halted=budget.trading_halted,
            remaining_exposure=budget.remaining_exposure,
        )
        return state
