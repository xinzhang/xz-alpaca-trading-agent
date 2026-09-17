import pytest

from alphadesk.clients.alpaca_client import AccountSnapshot, PositionSnapshot
from alphadesk.config import Settings
from alphadesk.risk_rules import compute_risk_budget, evaluate_order
from alphadesk.state import DecisionResult


def _settings(**overrides) -> Settings:
    defaults = dict(
        ALPACA_API_KEY="k",
        ALPACA_SECRET_KEY="s",
        OPENAI_API_KEY="k",
        PINECONE_API_KEY="k",
        TAVILY_API_KEY="k",
        MAX_POSITION_PCT=0.15,
        MAX_TOTAL_EXPOSURE_PCT=0.60,
        MAX_DRAWDOWN_PCT=0.10,
    )
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def _account(equity: float = 100_000.0) -> AccountSnapshot:
    return AccountSnapshot(equity=equity, cash=equity, buying_power=equity, portfolio_value=equity)


def test_no_drawdown_when_equity_at_peak():
    budget = compute_risk_budget(_account(100_000), {}, peak_equity=100_000, settings=_settings())
    assert budget.drawdown_pct == 0.0
    assert not budget.trading_halted


def test_trading_halts_once_drawdown_exceeds_limit():
    budget = compute_risk_budget(_account(89_000), {}, peak_equity=100_000, settings=_settings())
    assert budget.drawdown_pct == pytest.approx(0.11)
    assert budget.trading_halted
    assert budget.halt_reason is not None


def test_remaining_exposure_accounts_for_existing_positions():
    positions = {"AAPL": PositionSnapshot("AAPL", 10, 40_000, 4000, 0)}
    budget = compute_risk_budget(_account(100_000), positions, 100_000, _settings())
    # max exposure = 60_000; 40_000 already used -> 20_000 remaining
    assert budget.remaining_exposure == pytest.approx(20_000)


def test_evaluate_order_hold_is_always_approved():
    budget = compute_risk_budget(_account(100_000), {}, 100_000, _settings())
    decision = DecisionResult(action="HOLD", confidence=1.0, rationale="")
    verdict = evaluate_order(budget, "AAPL", {}, decision, "HOLD")
    assert verdict.approved


def test_evaluate_order_sell_without_position_is_rejected():
    budget = compute_risk_budget(_account(100_000), {}, 100_000, _settings())
    decision = DecisionResult(action="SELL", confidence=1.0, rationale="")
    verdict = evaluate_order(budget, "AAPL", {}, decision, "SELL")
    assert not verdict.approved


def test_evaluate_order_sell_closes_the_whole_position_by_qty():
    positions = {"AAPL": PositionSnapshot("AAPL", 10, 4_000, 400, 0)}
    budget = compute_risk_budget(_account(100_000), positions, 100_000, _settings())
    decision = DecisionResult(action="SELL", confidence=1.0, rationale="")

    verdict = evaluate_order(budget, "AAPL", positions, decision, "SELL")

    assert verdict.approved
    assert verdict.approved_qty == pytest.approx(10)
    assert verdict.approved_notional is None


def test_evaluate_order_sell_refunds_exposure_budget_for_later_tickers():
    positions = {"AAPL": PositionSnapshot("AAPL", 10, 40_000, 4_000, 0)}
    budget = compute_risk_budget(_account(100_000), positions, 100_000, _settings())
    assert budget.remaining_exposure == pytest.approx(20_000)  # 60_000 - 40_000

    sell = evaluate_order(budget, "AAPL", positions, DecisionResult("SELL", 1.0, ""), "SELL")
    assert sell.approved
    assert budget.remaining_exposure == pytest.approx(60_000)  # 20_000 + 40_000 freed

    buy_decision = DecisionResult(
        action="BUY", confidence=1.0, rationale="", target_notional=15_000
    )
    buy = evaluate_order(budget, "NVDA", positions, buy_decision, "BUY")
    assert buy.approved
    assert buy.approved_notional == pytest.approx(15_000)


def test_evaluate_order_buy_blocked_when_trading_halted():
    budget = compute_risk_budget(_account(89_000), {}, 100_000, _settings())
    decision = DecisionResult(action="BUY", confidence=1.0, rationale="", target_notional=1000)
    verdict = evaluate_order(budget, "AAPL", {}, decision, "BUY")
    assert not verdict.approved
    assert "drawdown" in verdict.reason


def test_evaluate_order_buy_caps_at_max_position_size():
    budget = compute_risk_budget(_account(100_000), {}, 100_000, _settings())
    decision = DecisionResult(action="BUY", confidence=1.0, rationale="", target_notional=50_000)
    verdict = evaluate_order(budget, "AAPL", {}, decision, "BUY")
    # max_position_notional = 15% of 100_000 = 15_000
    assert verdict.approved
    assert verdict.approved_notional == pytest.approx(15_000)


def test_evaluate_order_decrements_remaining_exposure_budget():
    budget = compute_risk_budget(_account(100_000), {}, 100_000, _settings())
    decision = DecisionResult(action="BUY", confidence=1.0, rationale="", target_notional=15_000)

    first = evaluate_order(budget, "AAPL", {}, decision, "BUY")
    assert first.approved_notional == pytest.approx(15_000)
    assert budget.remaining_exposure == pytest.approx(45_000)  # 60_000 - 15_000

    second = evaluate_order(budget, "NVDA", {}, decision, "BUY")
    assert second.approved_notional == pytest.approx(15_000)
    assert budget.remaining_exposure == pytest.approx(30_000)


def test_evaluate_order_buy_rejected_once_exposure_budget_exhausted():
    settings = _settings(MAX_TOTAL_EXPOSURE_PCT=0.10)
    budget = compute_risk_budget(_account(100_000), {}, 100_000, settings)
    decision = DecisionResult(action="BUY", confidence=1.0, rationale="", target_notional=15_000)

    first = evaluate_order(budget, "AAPL", {}, decision, "BUY")
    assert first.approved  # uses up the entire 10_000 exposure budget (capped below target)

    second = evaluate_order(budget, "NVDA", {}, decision, "BUY")
    assert not second.approved
    assert "exposure_room" in second.reason
