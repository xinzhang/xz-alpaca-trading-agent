"""No-op stand-ins for clients a backtest doesn't need real infra for.

A backtest run has no live dashboard to stream to, and shouldn't write backtest-era
news embeddings into the same Pinecone index the live system reads from — so these
satisfy the same call sites as the real EventBus/PineconeNewsStore without touching
Redis or Pinecone at all.
"""

from typing import Any


class NullEventBus:
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        pass

    async def close(self) -> None:
        pass


class NullPineconeStore:
    def upsert_articles(
        self, ticker: str, articles: list[dict[str, Any]], embeddings: list[list[float]]
    ) -> None:
        pass

    def query_recent(self, ticker: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        # Empty result makes SentimentAgent fall back to the freshly-fetched articles'
        # own titles — see sentiment_agent.py's `headlines = [...] or [...]` fallback.
        return []
