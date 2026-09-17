"""ORM models. `ts` is the hypertable partition column on every time-series table.

`id` is a UUID string with a Python-side default, not a DB-generated autoincrement
integer — SQLite refuses autoincrement on a composite primary key, and `(id, ts)` has
to stay composite because TimescaleDB requires the partition column in every unique
constraint on a hypertable. A Python-side default sidesteps both constraints identically
on Postgres (production) and SQLite (backtests) with no per-call-site changes.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from alphadesk.db.base import Base


def _new_id() -> str:
    return str(uuid4())

# Tables partitioned into TimescaleDB hypertables by `create_hypertable(<table>, 'ts')`.
HYPERTABLES = ["portfolio_snapshots", "agent_log_entries", "trade_fills", "decisions"]


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    buying_power: Mapped[float] = mapped_column(Float)
    portfolio_value: Mapped[float] = mapped_column(Float)
    peak_equity: Mapped[float] = mapped_column(Float)
    drawdown_pct: Mapped[float] = mapped_column(Float)


class AgentLogEntry(Base):
    """Generic per-node log line, powers the live activity feed on the dashboard."""

    __tablename__ = "agent_log_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    node: Mapped[str] = mapped_column(String(32))
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    message: Mapped[str] = mapped_column(String(512))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(8))  # BUY / SELL / HOLD
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(String(1024))
    risk_approved: Mapped[bool] = mapped_column(Boolean)
    risk_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)


class TradeFill(Base):
    __tablename__ = "trade_fills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(4))  # buy / sell
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    notional: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_id: Mapped[str] = mapped_column(String(64))
    dry_run: Mapped[bool] = mapped_column(Boolean)
