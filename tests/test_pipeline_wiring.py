"""Verifies LangGraph's per-node partial-update merge actually preserves nested
dataclass fields (TickerState, RiskBudget, ...) across a full cycle — this is the one
part of the orchestration unit tests on pure functions can't reach.
"""

from alphadesk.clients.alpaca_client import AccountSnapshot
from alphadesk.indicators import TechnicalSnapshot
from alphadesk.pipeline import TradingPipeline
from alphadesk.state import DecisionResult, PipelineState, RiskBudget, SentimentResult


class _FakeSignal:
    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            state.ticker_states[ticker].technical = TechnicalSnapshot(
                last_price=100.0, rsi_14=50.0, sma_20=99.0, ema_20=99.5,
                bollinger_upper=105.0, bollinger_lower=95.0,
            )
        return state


class _FakeRisk:
    async def run(self, state: PipelineState) -> PipelineState:
        account = AccountSnapshot(
            equity=100_000, cash=100_000, buying_power=100_000, portfolio_value=100_000
        )
        state.risk_budget = RiskBudget(
            account=account, peak_equity=100_000, drawdown_pct=0.0, trading_halted=False,
            halt_reason=None, max_position_notional=15_000, remaining_exposure=60_000,
        )
        return state


class _FakeSentiment:
    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            state.ticker_states[ticker].sentiment = SentimentResult(
                label="bullish", score=0.5, headlines=["fake headline"]
            )
        return state


class _FakeDecision:
    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            state.ticker_states[ticker].decision = DecisionResult(
                action="BUY", confidence=0.8, rationale="fake", target_notional=1000
            )
        return state


class _FakeExecution:
    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            state.ticker_states[ticker].executed = True
            state.ticker_states[ticker].order_id = f"FAKE-{ticker}"
        return state


async def test_full_cycle_preserves_every_nodes_contribution_per_ticker():
    pipeline = TradingPipeline(
        _FakeSignal(), _FakeRisk(), _FakeSentiment(), _FakeDecision(), _FakeExecution()
    )

    result = await pipeline.run_cycle(["AAPL", "NVDA"])

    for ticker in ["AAPL", "NVDA"]:
        ts = result.ticker_states[ticker]
        assert ts.technical is not None and ts.technical.last_price == 100.0
        assert ts.sentiment is not None and ts.sentiment.label == "bullish"
        assert ts.decision is not None and ts.decision.action == "BUY"
        assert ts.executed is True
        assert ts.order_id == f"FAKE-{ticker}"

    assert result.risk_budget is not None
    assert result.risk_budget.remaining_exposure == 60_000
