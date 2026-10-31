"""Sentiment must be based on fresh, real news about what the asset tracks — not quote
pages, stale results, or the Pinecone archive (the IAU-reads-as-neutral regression).
"""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from alphadesk.agents.sentiment_agent import SentimentAgent
from alphadesk.backtest.null_clients import NullEventBus, NullPineconeStore
from alphadesk.clients.tavily_client import TavilyNewsClient
from alphadesk.news_topics import describe_asset, news_query


def _ago(hours: float) -> str:
    return format_datetime(datetime.now(UTC) - timedelta(hours=hours), usegmt=True)


# What Tavily actually returned for "IAU stock news" on 2026-10-31, plus one real article.
_IAU_RESULTS = [
    {"title": "IAU Oct 2026 78.000 call (IAU261030C00078000) stock price, news, quote and "
              "history - Yahoo Finance",
     "url": "https://uk.finance.yahoo.com/quote/IAU261030C00078000", "published_date": _ago(3)},
    {"title": "iShares Gold Trust (IAU) Stock Price, News, Quote & History - Yahoo Finance",
     "url": "https://ca.finance.yahoo.com/quote/IAU", "published_date": _ago(5)},
    {"title": "Gold Futures (DEC6) Price Trend Today | Quotes & News",
     "url": "https://www.example.com/news/gold-futures", "published_date": _ago(4)},
    {"title": "Gold hits 3-1/2-month low on Fed hike fears",
     "url": "https://www.kitco.com/news/gold-low", "published_date": _ago(200),
     "content": "stale"},
    {"title": "Gold prices plunge to one-year low below $3,900", "content": "Spot gold fell 3%.",
     "url": "https://www.kitco.com/news/gold-plunge", "published_date": _ago(10)},
    {"title": "Gold prices plunge to one-year low below $3,900", "content": "Syndicated copy.",
     "url": "https://biztoc.com/x/gold-plunge", "published_date": _ago(9)},
    {"title": "Gold slips below $4,000", "content": "Earlier in the day.",
     "url": "https://finance.yahoo.com/gold-slips", "published_date": _ago(20)},
]


class _FakeTavily:
    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str, **kwargs) -> dict:
        self.queries.append(query)
        return {"results": self.results}


def _tavily_client(results: list[dict]) -> tuple[TavilyNewsClient, _FakeTavily]:
    client = TavilyNewsClient.__new__(TavilyNewsClient)
    client._client = _FakeTavily(results)
    client._max_age = timedelta(hours=48)
    return client, client._client


def test_etfs_search_for_what_they_track():
    assert news_query("IAU") == "gold price news"
    assert news_query("aapl") == "aapl stock news"
    assert describe_asset("IAU") == "IAU (ETF tracking gold price)"


def test_fetch_news_drops_quote_pages_stale_results_and_duplicates():
    client, fake = _tavily_client(_IAU_RESULTS)

    articles = client.fetch_news("IAU")

    assert fake.queries == ["gold price news"]
    assert [a["title"] for a in articles] == [
        "Gold prices plunge to one-year low below $3,900",
        "Gold slips below $4,000",
    ]
    assert articles[0]["url"] == "https://www.kitco.com/news/gold-plunge"


class _RecordingOpenAI:
    def __init__(self, label: str = "bearish", score: float = -0.6) -> None:
        self.label, self.score = label, score
        self.user_prompts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def decide(self, system_prompt: str, user_prompt: str, json_schema: dict) -> dict:
        self.user_prompts.append(user_prompt)
        return {"rationale": "gold fell", "label": self.label, "score": self.score}


class _StaticNews:
    def __init__(self, articles: list[dict]) -> None:
        self.articles = articles

    def fetch_news(self, ticker: str, max_results: int = 5) -> list[dict]:
        return self.articles


def _agent(articles: list[dict], openai: _RecordingOpenAI) -> SentimentAgent:
    return SentimentAgent(None, NullEventBus(), _StaticNews(articles), openai,
                          NullPineconeStore())


def test_classify_reads_fetched_articles_with_dates_and_snippets():
    openai = _RecordingOpenAI()
    articles = [{"id": "1", "title": "Gold plunges", "content": "Spot gold   fell 3%.",
                 "url": "https://example.com/1", "published_at": "Fri, 30 Oct 2026 18:00:00 GMT"}]

    result, returned = _agent(articles, openai).classify(
        "IAU", now=datetime(2026, 10, 31, 12, tzinfo=UTC)
    )

    assert (result.label, result.score, result.headlines) == ("bearish", -0.6, ["Gold plunges"])
    assert returned == articles
    prompt = openai.user_prompts[0]
    assert "Asset: IAU (ETF tracking gold price)" in prompt
    assert "Current time: Sat, 31 Oct 2026 12:00 UTC" in prompt
    assert "[Fri, 30 Oct 2026 18:00:00 GMT] Gold plunges" in prompt
    assert "Spot gold fell 3%." in prompt


def test_no_news_is_insufficient_not_neutral():
    openai = _RecordingOpenAI()
    result, articles = _agent([], openai).classify("IAU")
    assert (result.label, result.score, articles) == ("insufficient_news", 0.0, [])
    assert openai.user_prompts == []


def test_insufficient_news_label_forces_zero_score():
    openai = _RecordingOpenAI(label="insufficient_news", score=0.3)
    articles = [{"id": "1", "title": "t", "content": "", "url": "u", "published_at": ""}]
    result, _ = _agent(articles, openai).classify("IAU")
    assert (result.label, result.score) == ("insufficient_news", 0.0)
