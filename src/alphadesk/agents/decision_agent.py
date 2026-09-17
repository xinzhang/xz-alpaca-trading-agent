"""Decision Node ("the Brain"): synthesizes signal + sentiment + risk context into one
LLM call per ticker, returning a structured BUY/SELL/HOLD action + rationale.

This node only *proposes* — it does not enforce risk limits. ExecutionAgent is the
last, hard-coded gate before capital moves, so a confidently-wrong LLM output can
never bypass the caps computed in RiskAgent.
"""

from typing import Any

from alphadesk.agents.base import AgentNode
from alphadesk.clients.alpaca_client import PositionSnapshot
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.clients.redis_bus import EventBus
from alphadesk.db.base import Database
from alphadesk.state import DecisionResult, PipelineState

_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
        "target_notional": {"type": ["number", "null"]},
    },
    "required": ["action", "confidence", "rationale", "target_notional"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are a disciplined equity trading decision-maker for a paper-trading simulation. "
    "You receive technical indicators, news sentiment, current position, and hard risk "
    "constraints for one ticker. Decide BUY, SELL, or HOLD. You cannot exceed the stated "
    "risk constraints — they will be enforced regardless of your answer, so factor them "
    "into your reasoning rather than ignoring them. Prefer HOLD when signals conflict."
)


class DecisionAgent(AgentNode):
    name = "decision"

    def __init__(self, db: Database, event_bus: EventBus, openai: OpenAIClient) -> None:
        super().__init__(db, event_bus)
        self._openai = openai

    @staticmethod
    def _position_summary(position: PositionSnapshot | None) -> str:
        if position is None:
            return "none"
        return (
            f"{position.qty} shares, market_value=${position.market_value:.2f}, "
            f"unrealized_pl=${position.unrealized_pl:.2f}"
        )

    def _build_prompt(self, state: PipelineState, ticker: str) -> str:
        ts = state.ticker_states[ticker]
        technical, sentiment = ts.technical, ts.sentiment
        position = state.positions.get(ticker)
        budget = state.risk_budget

        return (
            f"Ticker: {ticker}\n"
            f"Technical: last_price={technical.last_price:.2f}, rsi_14={technical.rsi_14}, "
            f"sma_20={technical.sma_20}, ema_20={technical.ema_20}, "
            f"bollinger=({technical.bollinger_lower}, {technical.bollinger_upper})\n"
            f"Sentiment: label={sentiment.label}, score={sentiment.score:.2f}, "
            f"headlines={sentiment.headlines}\n"
            f"Current position: {self._position_summary(position)}\n"
            f"Risk constraints: trading_halted={budget.trading_halted} "
            f"({budget.halt_reason}), max_position_notional=${budget.max_position_notional:.2f}, "
            f"remaining_exposure_budget=${budget.remaining_exposure:.2f}, "
            f"account_buying_power=${budget.account.buying_power:.2f}"
        )

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            ts = state.ticker_states[ticker]
            if ts.technical is None or ts.sentiment is None:
                await self._log("missing upstream data, defaulting to HOLD", ticker=ticker)
                ts.decision = DecisionResult(
                    action="HOLD", confidence=1.0, rationale="missing data"
                )
                continue

            raw = self._openai.decide(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=self._build_prompt(state, ticker),
                json_schema=_DECISION_SCHEMA,
            )
            ts.decision = DecisionResult(
                action=raw["action"],
                confidence=float(raw["confidence"]),
                rationale=raw["rationale"],
                target_notional=raw["target_notional"],
            )
            await self._log(
                "decided",
                ticker=ticker,
                action=raw["action"],
                confidence=raw["confidence"],
                rationale=raw["rationale"],
            )
        return state
