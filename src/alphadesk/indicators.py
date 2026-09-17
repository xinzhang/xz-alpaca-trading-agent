"""Pure pandas technical indicators — no compiled dependencies (e.g. TA-Lib) required."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class TechnicalSnapshot:
    last_price: float
    rsi_14: float | None
    sma_20: float | None
    ema_20: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))

    # avg_loss == 0 is not "undefined" like a normal division by zero — it means every
    # move over the window was a gain, which is the textbook RSI == 100 case (or 50 if
    # there were no moves at all, i.e. avg_gain is also 0).
    no_losses = avg_loss == 0
    result = result.where(~no_losses, np.where(avg_gain == 0, 50.0, 100.0))
    return result


def sma(close: pd.Series, period: int = 20) -> pd.Series:
    return close.rolling(window=period).mean()


def ema(close: pd.Series, period: int = 20) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series]:
    mid = sma(close, period)
    std = close.rolling(window=period).std()
    return mid + num_std * std, mid - num_std * std


def _last_or_none(series: pd.Series) -> float | None:
    if series.empty or pd.isna(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def compute_snapshot(bars: pd.DataFrame) -> TechnicalSnapshot:
    """`bars` must have a `close` column, chronologically ordered."""
    close = bars["close"]
    upper, lower = bollinger_bands(close)
    return TechnicalSnapshot(
        last_price=float(close.iloc[-1]),
        rsi_14=_last_or_none(rsi(close)),
        sma_20=_last_or_none(sma(close)),
        ema_20=_last_or_none(ema(close)),
        bollinger_upper=_last_or_none(upper),
        bollinger_lower=_last_or_none(lower),
    )
