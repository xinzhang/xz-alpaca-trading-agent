"""A mutable 'now' shared by SimulatedBroker and HistoricalNewsClient during a backtest.

The runner advances `.now` once per simulated cycle; both clients read the same
instance so they always agree on what date is currently being replayed.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SimulatedClock:
    now: datetime
