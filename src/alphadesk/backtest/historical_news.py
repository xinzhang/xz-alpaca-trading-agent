"""Replaces TavilyNewsClient during a backtest: same `fetch_news(ticker, max_results)`
shape, but sourced from Alpaca's own historical News API (real publish timestamps),
filtered to articles published on or before the simulated 'now' — no lookahead.
"""

import hashlib
from typing import Any

from alphadesk.backtest.clock import SimulatedClock


class HistoricalNewsClient:
    def __init__(
        self, clock: SimulatedClock, preloaded_articles: dict[str, list[dict[str, Any]]]
    ) -> None:
        self._clock = clock
        # Each ticker's articles, pre-sorted ascending by published_at.
        self._articles = preloaded_articles

    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
        available = [
            a for a in self._articles.get(ticker, []) if a["published_at"] <= self._clock.now
        ]
        return available[-max_results:][::-1]  # most recent first, matching TavilyNewsClient


def to_article_dict(headline: str, summary: str, url: str, created_at, article_id: int) -> dict:
    return {
        "id": hashlib.sha256(f"{article_id}".encode()).hexdigest()[:32],
        "title": headline,
        "content": summary,
        "url": url,
        "published_at": created_at,
    }
