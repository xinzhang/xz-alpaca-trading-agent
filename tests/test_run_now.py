"""A manual "Run now" while the market is closed must analyze and record decisions but
never queue an order — it would fill at the next open, not at the analyzed close.
"""

import pandas as pd
import pytest
from sqlalchemy import select
from test_pipeline_wiring import _FakeDecision, _FakeRisk, _FakeSentiment, _FakeSignal

from alphadesk.agents.execution_agent import ExecutionAgent
from alphadesk.clients.alpaca_client import regular_session
from alphadesk.config import Settings
from alphadesk.db.base import Database
from alphadesk.db.models import Decision, TradeFill
from alphadesk.pipeline import TradingPipeline
from alphadesk.scheduler import CycleInProgressError, Scheduler


class _Broker:
    def __init__(self, market_open: bool) -> None:
        self.market_open = market_open
        self.orders: list[tuple] = []

    def is_market_open(self) -> bool:
        return self.market_open

    def submit_market_order(self, symbol, side, qty=None, notional=None):
        self.orders.append((symbol, side, notional))
        return type("Order", (), {"id": f"ORD-{symbol}"})()


class _Bus:
    async def publish(self, event_type: str, payload: dict) -> None:
        pass


async def _scheduler(market_open: bool) -> tuple[Scheduler, _Broker, Database]:
    settings = Settings(
        _env_file=None, ALPACA_API_KEY="k", ALPACA_SECRET_KEY="s", OPENAI_API_KEY="k",
        PINECONE_API_KEY="k", TAVILY_API_KEY="k", DRY_RUN=False, TICKERS="AAPL",
    )
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_all()
    broker, bus = _Broker(market_open), _Bus()
    pipeline = TradingPipeline(
        _FakeSignal(), _FakeRisk(), _FakeSentiment(), _FakeDecision(),
        ExecutionAgent(db, bus, broker, settings),
    )
    return Scheduler(pipeline, broker, bus, settings), broker, db


async def test_run_now_with_market_closed_records_decisions_without_orders():
    scheduler, broker, db = await _scheduler(market_open=False)

    result = await scheduler.run_now()

    assert (result["market_open"], result["orders_enabled"]) == (False, False)
    assert [t["ticker"] for t in result["tickers"]] == ["AAPL"]
    assert broker.orders == []
    async with db.session() as session:
        decisions = (await session.execute(select(Decision))).scalars().all()
        fills = (await session.execute(select(TradeFill))).scalars().all()
    assert [(d.action, d.risk_approved, d.executed) for d in decisions] == [("BUY", True, False)]
    assert fills == []


async def test_run_now_with_market_open_places_approved_orders():
    scheduler, broker, _ = await _scheduler(market_open=True)
    result = await scheduler.run_now()
    assert result["orders_enabled"] is True
    assert [o[0] for o in broker.orders] == ["AAPL"]


async def test_run_now_rejects_overlapping_cycles():
    scheduler, _, _ = await _scheduler(market_open=False)
    async with scheduler._cycle_lock:
        with pytest.raises(CycleInProgressError):
            await scheduler.run_now()


def test_regular_session_drops_pre_and_post_market_bars():
    index = pd.DatetimeIndex(
        ["2026-10-30 09:29", "2026-10-30 09:30", "2026-10-30 15:59", "2026-10-30 16:00"],
        tz="America/New_York",
    ).tz_convert("UTC")
    bars = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=index)
    assert regular_session(bars)["close"].tolist() == [2.0, 3.0]
