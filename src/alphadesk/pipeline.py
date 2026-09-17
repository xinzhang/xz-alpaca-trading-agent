"""Wires the five agent nodes into a LangGraph StateGraph: a linear, deterministic
cycle — Signal -> Risk -> Sentiment -> Decision -> Execution -> END.

Per-ticker branching (BUY/SELL/HOLD, risk-approved or not) happens *inside* each node,
not as graph edges — decisions are made per-symbol, not per-cycle, so a single
conditional edge over "the" LLM output wouldn't fit a multi-ticker cycle.
"""

from dataclasses import asdict
from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph

from alphadesk.agents.decision_agent import DecisionAgent
from alphadesk.agents.execution_agent import ExecutionAgent
from alphadesk.agents.risk_agent import RiskAgent
from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.agents.signal_agent import SignalAgent
from alphadesk.state import PipelineState


class TradingPipeline:
    def __init__(
        self,
        signal_agent: SignalAgent,
        risk_agent: RiskAgent,
        sentiment_agent: SentimentAgent,
        decision_agent: DecisionAgent,
        execution_agent: ExecutionAgent,
    ) -> None:
        self._agents = {
            "signal": signal_agent,
            "risk": risk_agent,
            "sentiment": sentiment_agent,
            "decision": decision_agent,
            "execution": execution_agent,
        }
        self._graph = self._build_graph()

    def _build_graph(self):
        # Each agent mutates `state` in place and returns it; we translate that into an
        # explicit partial-update dict (rather than returning the object itself) so
        # nested dataclasses (TickerState, RiskBudget, ...) survive LangGraph's
        # per-field merge intact instead of being flattened/re-typed.
        updated_keys = {
            "signal": ("ticker_states",),
            "risk": ("positions", "risk_budget"),
            "sentiment": ("ticker_states",),
            "decision": ("ticker_states",),
            "execution": ("ticker_states", "risk_budget"),
        }

        def make_node(name: str, agent):
            keys = updated_keys[name]

            async def node(state: PipelineState) -> dict:
                new_state = await agent.run(state)
                return {key: getattr(new_state, key) for key in keys}

            return node

        builder = StateGraph(PipelineState)
        for name, agent in self._agents.items():
            builder.add_node(name, make_node(name, agent))

        builder.add_edge(START, "signal")
        builder.add_edge("signal", "risk")
        builder.add_edge("risk", "sentiment")
        builder.add_edge("sentiment", "decision")
        builder.add_edge("decision", "execution")
        builder.add_edge("execution", END)
        return builder.compile()

    async def run_cycle(self, tickers: list[str]) -> PipelineState:
        initial_state = PipelineState(cycle_ts=datetime.now(UTC), tickers=tickers)
        # `ainvoke` returns a plain dict of the final channel values, not a PipelineState
        # instance — rebuild it explicitly rather than relying on that implicit shape.
        raw: dict = await self._graph.ainvoke(initial_state)
        return PipelineState(
            cycle_ts=initial_state.cycle_ts,
            tickers=initial_state.tickers,
            positions=raw["positions"],
            risk_budget=raw["risk_budget"],
            ticker_states=raw["ticker_states"],
        )


def decision_summary(state: PipelineState) -> list[dict]:
    """Flat, JSON-serializable view of a completed cycle, for logging/dashboard payloads."""
    summary = []
    for ticker, ts in state.ticker_states.items():
        summary.append(
            {
                "ticker": ticker,
                "technical": asdict(ts.technical) if ts.technical else None,
                "sentiment": asdict(ts.sentiment) if ts.sentiment else None,
                "decision": asdict(ts.decision) if ts.decision else None,
                "risk_verdict": asdict(ts.risk_verdict) if ts.risk_verdict else None,
                "executed": ts.executed,
                "order_id": ts.order_id,
            }
        )
    return summary
