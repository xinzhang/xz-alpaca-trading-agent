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
    """`decision.target_notional` is the desired TOTAL position value after this
    decision, for both BUY and SELL — not an incremental amount. Direction always
    comes from `action`, never from the sign of the computed delta: a BUY whose
    target is already met, or a SELL whose target is already undercut, is a no-op
    rather than a trade in the opposite direction.
    """
    if action == "HOLD":
        return RiskVerdict(approved=True, reason=None)

    if action == "SELL":
        position = positions.get(ticker)
        if position is None:
            return RiskVerdict(approved=False, reason="no existing position to sell")

        current_value = position.market_value
        # No stated target defaults to a full exit, same as before this change.
        target = max(0.0, min(decision.target_notional or 0.0, current_value))
        delta = target - current_value
        if delta >= 0:
            return RiskVerdict(approved=True, reason="already at or below target")

        sell_notional = min(-delta, current_value)
        # Frees that much exposure budget for tickers still to come in this cycle.
        budget.remaining_exposure += sell_notional
        return RiskVerdict(approved=True, reason=None, approved_notional=sell_notional)

    # action == "BUY"
    if budget.trading_halted:
        return RiskVerdict(approved=False, reason=budget.halt_reason)

    current_position = positions.get(ticker)
    current_value = current_position.market_value if current_position else 0.0

    # The cap always wins, regardless of what the model asked for.
    requested = decision.target_notional or budget.max_position_notional
    target = min(requested, budget.max_position_notional)
    delta = target - current_value
    if delta <= 0:
        return RiskVerdict(approved=True, reason="target already met")

    approved_notional = min(delta, budget.remaining_exposure)
    if approved_notional <= 0:
        return RiskVerdict(
            approved=False,
            reason=(
                f"no capacity: position_room=${delta:.2f}, "
                f"exposure_room=${budget.remaining_exposure:.2f}"
            ),
        )

    budget.remaining_exposure -= approved_notional
    return RiskVerdict(approved=True, reason=None, approved_notional=approved_notional)
