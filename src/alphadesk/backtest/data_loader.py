"""Bulk-fetches everything a backtest needs up front: one API call per ticker for bars,
one paginated pull per ticker for news — rather than one call per simulated cycle.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alphadesk.backtest.config import BacktestConfig
from alphadesk.config import Settings


def _to_utc_datetime(d: date, end_of_day: bool = False) -> datetime:
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=UTC)


def load_historical_bars(settings: Settings, config: BacktestConfig) -> dict[str, pd.DataFrame]:
    client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    fetch_start = config.start - timedelta(days=config.lookback_buffer_days)

    feed = DataFeed.SIP if settings.alpaca_data_feed.upper() == "SIP" else DataFeed.IEX
    request = StockBarsRequest(
        symbol_or_symbols=config.tickers,
        timeframe=TimeFrame.Day,
        start=_to_utc_datetime(fetch_start),
        end=_to_utc_datetime(config.end, end_of_day=True),
        feed=feed,
    )
    bars = client.get_stock_bars(request).df

    result = {}
    for ticker in config.tickers:
        ticker_bars = bars.xs(ticker, level="symbol") if "symbol" in bars.index.names else bars
        result[ticker] = ticker_bars.sort_index()
    return result


def load_historical_news(
    settings: Settings, config: BacktestConfig
) -> dict[str, list[dict[str, Any]]]:
    client = NewsClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    start = _to_utc_datetime(config.start)
    end = _to_utc_datetime(config.end, end_of_day=True)

    # `limit` here is a TOTAL count, not a per-page size — the client already paginates
    # internally (in pages of 50) up to this total. A manual page_token loop is
    # unnecessary and doesn't work anyway: NewsSet doesn't expose one.
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker in config.tickers:
        request = NewsRequest(symbols=ticker, start=start, end=end, limit=2500)
        response = client.get_news(request)
        articles = [
            {
                "id": str(article.id),
                "title": article.headline,
                "content": article.summary or article.headline,
                "url": article.url,
                "published_at": article.created_at,
            }
            for article in response.data["news"]
        ]
        result[ticker] = sorted(articles, key=lambda a: a["published_at"])
    return result


def trading_days(bars: dict[str, pd.DataFrame], config: BacktestConfig) -> list[pd.Timestamp]:
    """Uses the first ticker's own bar dates as the walk-forward calendar — bars from
    Alpaca already exclude weekends/holidays, so no separate market-calendar call needed.
    """
    any_ticker = config.tickers[0]
    index = bars[any_ticker].index
    start_ts = pd.Timestamp(config.start, tz="UTC")
    end_ts = pd.Timestamp(config.end, tz="UTC") + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return [ts for ts in index if start_ts <= ts <= end_ts]
