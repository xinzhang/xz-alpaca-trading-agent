"""Thin wrapper around Tavily: fetches recent news articles per ticker, dropping quote
pages and anything older than `max_age`."""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from tavily import TavilyClient as _TavilyClient

from alphadesk.config import Settings
from alphadesk.news_topics import news_query

# Tavily's "news" topic happily returns quote/options-chain pages for a bare ticker;
# they carry no sentiment and crowd out real articles.
_JUNK_URL = re.compile(r"/quote/|/quotes/|/symbols/|/etfs?/[a-z]+/?$", re.IGNORECASE)
_JUNK_TITLE = re.compile(
    r"stock price, news, quote|price, chart & news|quote & history|quotes & news|"
    r"\b[A-Z]{1,5}\d{6}[CP]\d{8}\b",  # OCC option symbol, e.g. IAU261030C00078000
    re.IGNORECASE,
)


def parse_published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_junk(title: str, url: str) -> bool:
    return bool(_JUNK_URL.search(url) or _JUNK_TITLE.search(title))


class TavilyNewsClient:
    def __init__(self, settings: Settings, max_age: timedelta = timedelta(hours=48)) -> None:
        self._client = _TavilyClient(api_key=settings.tavily_api_key)
        self._max_age = max_age

    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Most recent first. Over-fetches since filtering typically drops a third or more."""
        response = self._client.search(
            query=news_query(ticker),
            topic="news",
            search_depth="advanced",
            max_results=max_results * 3,
            days=2,
        )
        cutoff = datetime.now(UTC) - self._max_age
        dated: list[tuple[datetime, dict[str, Any]]] = []
        seen_titles: set[str] = set()
        for result in response.get("results", []):
            title, url = result.get("title", ""), result["url"]
            published = parse_published(result.get("published_date", ""))
            # `days=2` isn't reliably enforced server-side, so check it here too.
            if is_junk(title, url) or published is None or published < cutoff:
                continue
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            dated.append((published, {
                "id": hashlib.sha256(url.encode()).hexdigest()[:32],
                "title": title,
                "content": result.get("content", ""),
                "url": url,
                "published_at": result.get("published_date", ""),
            }))
        dated.sort(key=lambda pair: pair[0], reverse=True)
        return [article for _, article in dated[:max_results]]
