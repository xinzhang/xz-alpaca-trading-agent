"""Pure, hard-coded risk logic — no LLM involved. Deliberately independent of decision.py
so a bad model output can never talk its way past a limit.

Two entry points:
- `compute_risk_budget`: called once per cycle by RiskAgent, from real account state.
- `evaluate_order`: called once per approved-candidate ticker by ExecutionAgent, right
  before an order would be submitted. Mutates `budget.remaining_exposure` on approval so
  later tickers in the same cycle see a tighter budget (first-come-first-served ordering).
"""

from alphadesk.clients.alpaca_client import AccountSnapshot, PositionSnapshot
from alphadesk.config import Settings
from alphadesk.state import Action, DecisionResult, RiskBudget, RiskVerdict


def compute_risk_budget(
    account: AccountSnapshot,
    positions: dict[str, PositionSnapshot],
    peak_equity: float,
    settings: Settings,
) -> RiskBudget:
    peak_equity = max(peak_equity, account.equity)
    drawdown_pct = max(0.0, (peak_equity - account.equity) / peak_equity) if peak_equity else 0.0
    trading_halted = drawdown_pct >= settings.max_drawdown_pct

    total_position_value = sum(p.market_value for p in positions.values())
    max_total_exposure = settings.max_total_exposure_pct * account.equity
    remaining_exposure = max(0.0, max_total_exposure - total_position_value)

    return RiskBudget(
        account=account,
        peak_equity=peak_equity,
        drawdown_pct=drawdown_pct,
        trading_halted=trading_halted,
        halt_reason=(
            f"drawdown {drawdown_pct:.1%} >= limit {settings.max_drawdown_pct:.1%}"
            if trading_halted
            else None
        ),
        max_position_notional=settings.max_position_pct * account.equity,
        remaining_exposure=remaining_exposure,
    )


def evaluate_order(
    budget: RiskBudget,
    ticker: str,
    positions: dict[str, PositionSnapshot],
    decision: DecisionResult,
    action: Action,
) -> RiskVerdict:
    if action == "HOLD":
        return RiskVerdict(approved=True, reason=None)

    if action == "SELL":
        position = positions.get(ticker)
        if position is None:
            return RiskVerdict(approved=False, reason="no existing position to sell")
        # Closing the whole position frees that much exposure budget for tickers still
        # to come in this same cycle.
        budget.remaining_exposure += position.market_value
        return RiskVerdict(approved=True, reason=None, approved_qty=position.qty)

    # action == "BUY"
    if budget.trading_halted:
        return RiskVerdict(approved=False, reason=budget.halt_reason)

    requested = decision.target_notional or budget.max_position_notional
    current_position_value = positions.get(ticker)
    current_value = current_position_value.market_value if current_position_value else 0.0

    room_in_position = max(0.0, budget.max_position_notional - current_value)
    approved_notional = min(requested, room_in_position, budget.remaining_exposure)

    if approved_notional <= 0:
        return RiskVerdict(
            approved=False,
            reason=(
                f"no capacity: position_room=${room_in_position:.2f}, "
                f"exposure_room=${budget.remaining_exposure:.2f}"
            ),
        )

    budget.remaining_exposure -= approved_notional
    return RiskVerdict(approved=True, reason=None, approved_notional=approved_notional)
