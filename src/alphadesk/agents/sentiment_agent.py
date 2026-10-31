"""Sentiment Node ("the Qualitative Engine"): Tavily news -> LLM classification into
bullish / bearish / neutral, or insufficient_news when nothing fetched is actual news.

Fetched articles are archived in Pinecone (OpenAI embeddings), but classification reads
only the articles fetched this run: similarity retrieval over the archive surfaced stale
and unrelated headlines (e.g. IAUX for IAU) in place of today's news.
"""

from datetime import UTC, datetime
from typing import Any

from alphadesk.agents.base import AgentNode
from alphadesk.clients.openai_client import OpenAIClient
from alphadesk.clients.protocols import EventPublisher, NewsSource, VectorStore
from alphadesk.db.base import Database
from alphadesk.news_topics import describe_asset
from alphadesk.state import PipelineState, SentimentResult

_SNIPPET_CHARS = 400

_SENTIMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rationale": {
            "type": "string",
            "description": (
                "Two to four sentences: which articles drive the call, which are noise, "
                "and why the overall tone lands where it does."
            ),
        },
        "label": {
            "type": "string",
            "enum": ["bullish", "bearish", "neutral", "insufficient_news"],
        },
        "score": {"type": "number"},
    },
    "required": ["rationale", "label", "score"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are a financial news sentiment classifier. Given recent articles about an asset "
    "(title, publish time, snippet), classify the sentiment for its price over the next "
    "few days as bullish, bearish, or neutral, with a score from -1.0 (very bearish) to "
    "1.0 (very bullish). For an ETF, news about what it tracks (e.g. the gold price for "
    "a gold ETF) is what matters. Weight newer articles more, and reported price moves "
    "and their drivers over evergreen or promotional pieces. Ignore quote pages, "
    "'how much $100 invested' style filler, and articles about a different company or "
    "ticker. Use neutral only when real news is genuinely mixed or flat. If no article "
    "is actual news about this asset or its drivers, answer insufficient_news with "
    "score 0 — that means 'no evidence', which is different from neutral."
)


def _format_articles(articles: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- [{a.get('published_at') or 'unknown time'}] {a['title']}\n"
        f"  {' '.join((a.get('content') or '').split())[:_SNIPPET_CHARS]}"
        for a in articles
    )


class SentimentAgent(AgentNode):
    name = "sentiment"

    def __init__(
        self,
        db: Database,
        event_bus: EventPublisher,
        tavily: NewsSource,
        openai: OpenAIClient,
        pinecone: VectorStore,
    ) -> None:
        super().__init__(db, event_bus)
        self._tavily = tavily
        self._openai = openai
        self._pinecone = pinecone

    def classify(
        self, ticker: str, now: datetime | None = None
    ) -> tuple[SentimentResult, list[dict[str, Any]]]:
        """Returns the classification plus the articles it was based on. Only side effect
        is archiving those articles in the vector store."""
        articles = self._tavily.fetch_news(ticker)
        if not articles:
            return SentimentResult(
                label="insufficient_news", score=0.0, headlines=[],
                rationale="no recent news found",
            ), []

        embeddings = self._openai.embed([a["title"] + " " + a["content"] for a in articles])
        self._pinecone.upsert_articles(ticker, articles, embeddings)

        now = now or datetime.now(UTC)
        classification = self._openai.decide(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=(
                f"Asset: {describe_asset(ticker)}\n"
                f"Current time: {now:%a, %d %b %Y %H:%M} UTC\n"
                f"Articles (newest first):\n{_format_articles(articles)}"
            ),
            json_schema=_SENTIMENT_SCHEMA,
        )
        label = classification["label"]
        return SentimentResult(
            label=label,
            score=0.0 if label == "insufficient_news" else float(classification["score"]),
            headlines=[a["title"] for a in articles],
            rationale=classification["rationale"],
        ), articles

    async def run(self, state: PipelineState) -> PipelineState:
        for ticker in state.tickers:
            sentiment, articles = self.classify(ticker, now=state.cycle_ts)
            state.ticker_states[ticker].sentiment = sentiment
            if not articles:
                await self._log("no news found", ticker=ticker)
                continue
            await self._log(
                "classified sentiment",
                ticker=ticker,
                label=sentiment.label,
                score=sentiment.score,
            )
        return state
