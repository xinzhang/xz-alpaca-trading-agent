"""Shared pipeline state that flows through the LangGraph nodes for a single cycle.

Each node mutates its own section of the state; downstream nodes read prior sections.
Tickers are evaluated independently but *within one cycle*, in `ticker` list order —
`RiskBudget.remaining_exposure` is decremented as each approved BUY is sized, so later
tickers in the same cycle see a tighter budget than earlier ones.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from alphadesk.clients.alpaca_client import AccountSnapshot, PositionSnapshot
from alphadesk.indicators import TechnicalSnapshot

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass(slots=True)
class RiskBudget:
    account: AccountSnapshot
    peak_equity: float
    drawdown_pct: float
    trading_halted: bool
    halt_reason: str | None
    max_position_notional: float
    remaining_exposure: float


@dataclass(slots=True)
class SentimentResult:
    label: Literal["bullish", "bearish", "neutral"]
    score: float  # -1.0 (very bearish) .. +1.0 (very bullish)
    headlines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DecisionResult:
    action: Action
    confidence: float
    rationale: str
    target_notional: float | None = None


@dataclass(slots=True)
class RiskVerdict:
    approved: bool
    reason: str | None
    approved_notional: float | None = None  # BUY sizing, in dollars
    approved_qty: float | None = None  # SELL sizing, in shares (closes the whole position)


@dataclass(slots=True)
class TickerState:
    ticker: str
    technical: TechnicalSnapshot | None = None
    sentiment: SentimentResult | None = None
    decision: DecisionResult | None = None
    risk_verdict: RiskVerdict | None = None
    executed: bool = False
    order_id: str | None = None


@dataclass(slots=True)
class PipelineState:
    cycle_ts: datetime
    tickers: list[str]
    positions: dict[str, PositionSnapshot] = field(default_factory=dict)
    risk_budget: RiskBudget | None = None
    ticker_states: dict[str, TickerState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for ticker in self.tickers:
            self.ticker_states.setdefault(ticker, TickerState(ticker=ticker))
