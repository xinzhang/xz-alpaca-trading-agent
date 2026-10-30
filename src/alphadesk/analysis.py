"""On-demand, single-symbol analysis for the dashboard's "Analyze" dialog.

Runs the same Signal -> Risk -> Sentiment -> Decision agents the scheduled cycle uses,
then the same hard-coded `evaluate_order` gate — but only to *report* what would
happen. Nothing is executed, persisted, or published to the live feed. A final LLM
call turns every agent's output into a human-readable summary.
"""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from alphadesk.agents.decision_agent import DecisionAgent
from alphadesk.agents.risk_agent import RiskAgent
from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.agents.signal_agent import SignalAgent
from alphadesk.clients.alpaca_client import PositionSnapshot
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.config import Settings
from alphadesk.indicators import TechnicalSnapshot
from alphadesk.risk_rules import evaluate_order
from alphadesk.state import PipelineState, RiskBudget

_STRING_LIST = {"type": "array", "items": {"type": "string"}}

_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence: the call and why."},
        "summary": {
            "type": "string",
            "description": "One paragraph walking through how the agents' outputs combine.",
        },
        "bull_case": _STRING_LIST,
        "bear_case": _STRING_LIST,
        "key_risks": _STRING_LIST,
        "what_would_change_the_call": _STRING_LIST,
    },
    "required": [
        "headline", "summary", "bull_case", "bear_case", "key_risks",
        "what_would_change_the_call",
    ],
    "additionalProperties": False,
}

_SUMMARY_SYSTEM_PROMPT = (
    "You explain an automated multi-agent trading pipeline's analysis of one stock to a "
    "human. You receive the technical signal, account risk budget, news sentiment, the "
    "decision agent's proposal, and the hard-coded risk gate's verdict. Do not make a new "
    "decision — explain the one that was made, faithfully, including where the evidence "
    "is weak or conflicting. Be concrete: cite the actual numbers and headlines. Note "
    "that the technical indicators are computed on recent 1-minute bars, i.e. intraday."
)


class SymbolAnalyzer:
    def __init__(
        self,
        settings: Settings,
        signal_agent: SignalAgent,
        risk_agent: RiskAgent,
        sentiment_agent: SentimentAgent,
        decision_agent: DecisionAgent,
        openai: OpenAIClient,
    ) -> None:
        self._settings = settings
        self._signal = signal_agent
        self._risk = risk_agent
        self._sentiment = sentiment_agent
        self._decision = decision_agent
        self._openai = openai

    async def analyze(self, symbol: str) -> dict[str, Any] | None:
        """Returns None when there's no market data for `symbol`. The blocking client
        calls run in a thread so a ~10s analysis doesn't stall the live dashboard."""
        technical, bar_count = await asyncio.to_thread(self._signal.compute, symbol)
        if technical is None:
            return None

        positions, budget = await self._risk.observe()
        risk_section = _describe_risk(budget, positions.get(symbol), self._settings)

        sentiment, articles = await asyncio.to_thread(self._sentiment.classify, symbol)

        state = PipelineState(
            cycle_ts=datetime.now(UTC), tickers=[symbol], positions=positions,
            risk_budget=budget,
        )
        state.ticker_states[symbol].technical = technical
        state.ticker_states[symbol].sentiment = sentiment
        decision_prompt = self._decision.build_prompt(state, symbol)
        decision = await asyncio.to_thread(self._decision.decide, state, symbol)

        # Mutates budget.remaining_exposure, which is fine: this budget is ours alone and
        # risk_section already captured the pre-verdict numbers.
        verdict = evaluate_order(budget, symbol, positions, decision, decision.action)

        result: dict[str, Any] = {
            "symbol": symbol,
            "ts": state.cycle_ts,
            "signal": {
                "bar_count": bar_count,
                "technical": asdict(technical),
                "observations": _describe_technical(technical),
            },
            "risk": risk_section,
            "sentiment": {
                "label": sentiment.label,
                "score": sentiment.score,
                "rationale": sentiment.rationale,
                "headlines": sentiment.headlines,
                "articles": [
                    {k: a.get(k) for k in ("title", "url", "published_at")} for a in articles
                ],
            },
            "decision": {**asdict(decision), "prompt": decision_prompt},
            "risk_check": {
                **asdict(verdict),
                "would_trade": bool(verdict.approved and verdict.approved_notional),
            },
        }
        result["summary"] = await asyncio.to_thread(self._summarize, result)
        return result

    def _summarize(self, result: dict[str, Any]) -> dict[str, Any]:
        sections = {k: result[k] for k in ("signal", "risk", "sentiment", "risk_check")}
        decision = {k: v for k, v in result["decision"].items() if k != "prompt"}
        return self._openai.decide(
            system_prompt=_SUMMARY_SYSTEM_PROMPT,
            user_prompt=f"Symbol: {result['symbol']}\n{sections}\ndecision={decision}",
            json_schema=_SUMMARY_SCHEMA,
        )


def _pct_diff(price: float, reference: float | None) -> str | None:
    if not reference:
        return None
    diff = (price - reference) / reference
    return f"{abs(diff):.2%} {'above' if diff >= 0 else 'below'}"


def _describe_technical(t: TechnicalSnapshot) -> list[str]:
    notes: list[str] = []
    if t.rsi_14 is not None:
        if t.rsi_14 >= 70:
            zone = "overbought — momentum is stretched, pullback risk is elevated"
        elif t.rsi_14 <= 30:
            zone = "oversold — selling may be exhausted, bounce potential"
        elif t.rsi_14 >= 55:
            zone = "neutral with bullish momentum"
        elif t.rsi_14 <= 45:
            zone = "neutral with bearish momentum"
        else:
            zone = "neutral, no clear momentum"
        notes.append(f"RSI(14) {t.rsi_14:.1f}: {zone}.")
    for name, reference in (("SMA(20)", t.sma_20), ("EMA(20)", t.ema_20)):
        if (diff := _pct_diff(t.last_price, reference)) is not None:
            notes.append(f"Price ${t.last_price:.2f} is {diff} its {name} (${reference:.2f}).")
    if t.bollinger_upper is not None and t.bollinger_lower is not None:
        width = t.bollinger_upper - t.bollinger_lower
        if width > 0:
            pct_b = (t.last_price - t.bollinger_lower) / width
            if pct_b > 1:
                where = "above the upper band — an unusually strong (or overextended) move"
            elif pct_b < 0:
                where = "below the lower band — an unusually weak (or oversold) move"
            elif pct_b >= 0.8:
                where = "near the upper band"
            elif pct_b <= 0.2:
                where = "near the lower band"
            else:
                where = "mid-band"
            notes.append(
                f"Bollinger %B {pct_b:.2f} ({where}); band width "
                f"{width / t.last_price:.2%} of price."
            )
    return notes


def _describe_risk(
    budget: RiskBudget, position: PositionSnapshot | None, settings: Settings
) -> dict[str, Any]:
    account = budget.account
    current_value = position.market_value if position else 0.0
    notes = [
        f"Equity ${account.equity:,.2f}, buying power ${account.buying_power:,.2f}.",
        f"Drawdown {budget.drawdown_pct:.2%} from peak ${budget.peak_equity:,.2f} "
        f"(halt limit {settings.max_drawdown_pct:.0%}).",
        "Trading HALTED: " + budget.halt_reason if budget.trading_halted
        else "Trading allowed — drawdown is under the limit.",
        f"Per-position cap ${budget.max_position_notional:,.2f} "
        f"({settings.max_position_pct:.0%} of equity); room left in this symbol "
        f"${max(0.0, budget.max_position_notional - current_value):,.2f}.",
        f"Total exposure cap {settings.max_total_exposure_pct:.0%} of equity; "
        f"${budget.remaining_exposure:,.2f} of it unused.",
    ]
    if position:
        notes.append(
            f"Holding {position.qty:g} shares worth ${position.market_value:,.2f} "
            f"(avg entry ${position.avg_entry_price:.2f}, unrealized P/L "
            f"${position.unrealized_pl:,.2f})."
        )
    else:
        notes.append("No existing position in this symbol.")
    return {
        "equity": account.equity,
        "buying_power": account.buying_power,
        "drawdown_pct": budget.drawdown_pct,
        "trading_halted": budget.trading_halted,
        "halt_reason": budget.halt_reason,
        "max_position_notional": budget.max_position_notional,
        "remaining_exposure": budget.remaining_exposure,
        "position": asdict(position) if position else None,
        "observations": notes,
    }
