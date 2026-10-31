"""What a ticker's price actually tracks, for news search and for the sentiment prompt.

ETF news rarely names the ticker: what moves IAU is written up as "gold", not "IAU",
so searching "IAU stock news" returns quote pages instead of news.
"""

ASSET_TOPICS: dict[str, str] = {
    "IAU": "gold price",
    "GLD": "gold price",
    "GLDM": "gold price",
    "SLV": "silver price",
    "USO": "crude oil price",
    "SPY": "S&P 500 stock market",
    "VOO": "S&P 500 stock market",
    "QQQ": "Nasdaq 100 stock market",
    "DIA": "Dow Jones stock market",
    "IWM": "Russell 2000 small cap stocks",
    "TLT": "long-term Treasury bond yields",
}


def news_query(ticker: str) -> str:
    topic = ASSET_TOPICS.get(ticker.upper())
    return f"{topic} news" if topic else f"{ticker} stock news"


def describe_asset(ticker: str) -> str:
    topic = ASSET_TOPICS.get(ticker.upper())
    return f"{ticker} (ETF tracking {topic})" if topic else ticker
