"""Sentiment Node ("the Qualitative Engine"): Tavily news -> OpenAI embeddings -> Pinecone
retrieval -> LLM classification into bullish / bearish / neutral.
"""

from typing import Any

from alphadesk.agents.base import AgentNode
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.clients.pinecone_client import PineconeNewsStore
from alphadesk.clients.redis_bus import EventBus
from alphadesk.clients.tavily_client import TavilyNewsClient
from alphadesk.db.base import Database
from alphadesk.state import PipelineState, SentimentResult

_SENTIMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "score": {"type": "number"},
    },
    "required": ["label", "score"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier. Given recent headlines for a stock "
    "ticker, classify overall sentiment as bullish, bearish, or neutral, and give a score "
    "from -1.0 (very bearish) to 1.0 (very bullish). Be conservative: if headlines are "
    "mixed or mostly noise, prefer neutral with a score near 0."
)


class SentimentAgent(AgentNode):
    name = "sentiment"

    def __init__(
        self,
        db: Database,
        event_bus: EventBus,
        tavily: TavilyNewsClient,
        openai: OpenAIClient,
        pinecone: PineconeNewsStore,
    ) -> None:
        super().__init__(db, event_bus)
        self._tavily = tavily
        self._openai = openai
        self._pinecone = pinecone

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            articles = self._tavily.fetch_news(ticker)
            if not articles:
                state.ticker_states[ticker].sentiment = SentimentResult(
                    label="neutral", score=0.0, headlines=[]
                )
                await self._log("no news found, defaulting to neutral", ticker=ticker)
                continue

            embeddings = self._openai.embed([a["title"] + " " + a["content"] for a in articles])
            self._pinecone.upsert_articles(ticker, articles, embeddings)

            retrieved = self._pinecone.query_recent(ticker, embeddings[0], top_k=5)
            headlines = [r["title"] for r in retrieved] or [a["title"] for a in articles]

            headline_list = "\n".join(f"- {h}" for h in headlines)
            classification = self._openai.decide(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=f"Ticker: {ticker}\nHeadlines:\n{headline_list}",
                json_schema=_SENTIMENT_SCHEMA,
            )
            state.ticker_states[ticker].sentiment = SentimentResult(
                label=classification["label"],
                score=float(classification["score"]),
                headlines=headlines,
            )
            await self._log(
                "classified sentiment",
                ticker=ticker,
                label=classification["label"],
                score=classification["score"],
            )
        return state
