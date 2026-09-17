# AlphaDesk-style Trading Agent

A multi-agent AI trading pipeline on Alpaca **paper trading**, inspired by the
[AlphaDesk case study](https://alpaca.markets/learn/building-alphadesk-a-multi-agent-ai-trading-system-case-study).
Educational / simulation only — not a live-trading system.

## Architecture

Five agents run in a fixed sequence, orchestrated by a LangGraph `StateGraph`, once per
cycle (default every 15 minutes, market hours only):

```
Signal -> Risk -> Sentiment -> Decision -> Execution
```

- **Signal** — pulls recent OHLCV bars from Alpaca and computes RSI/SMA/EMA/Bollinger Bands per ticker.
- **Risk** — reads real account state (equity, buying power, positions, drawdown from peak) and
  computes this cycle's hard-coded budget (max per-position size, max total exposure, drawdown halt).
- **Sentiment** — fetches recent news per ticker via Tavily, embeds it (OpenAI), stores/retrieves it
  in Pinecone, and classifies bullish/bearish/neutral.
- **Decision** — one OpenAI call per ticker, given technical + sentiment + risk context, returns a
  structured BUY/SELL/HOLD + rationale. It only *proposes* — see below.
- **Execution** — the last, hard-coded gate (`risk_rules.evaluate_order`). Enforces per-position and
  total-exposure caps and the drawdown halt *independently of the LLM's output*, then submits (or,
  if `DRY_RUN=true`, simulates) the order and logs the fill.

Risk enforcement only ever **blocks new BUYs** — it never force-liquidates an existing position.

Tickers are evaluated independently within a cycle and can hold concurrent positions; the exposure
budget is shared and decremented ticker-by-ticker in the configured order within that cycle.

## Stack

Python (LangGraph, FastAPI, SQLAlchemy async, alpaca-py) · Postgres/TimescaleDB · Redis (pub/sub) ·
Next.js dashboard · Docker Compose (local only for now).

## Setup

```bash
cp .env.example .env   # fill in ALPACA_*, OPENAI_API_KEY, PINECONE_API_KEY, TAVILY_API_KEY
uv sync
docker compose up -d timescaledb redis   # Postgres mapped to host 5433, not 5432, to
                                          # avoid clashing with any other local Postgres
uv run python scripts/init_db.py
uv run python -m alphadesk.main       # backend on :8001 (PORT in .env; 8000 was taken)
```

To force one pipeline cycle immediately, ignoring market hours (useful for testing):

```bash
uv run python scripts/run_once.py
```

Frontend:

```bash
cd frontend
cp .env.local.example .env.local       # points at the backend's port
npm install
npm run dev                            # dashboard on :3000
```

Or run everything (backend + frontend + infra) via `docker compose up --build`.

## Safety

`DRY_RUN=true` by default — the pipeline runs end-to-end and logs decisions, but never submits real
orders. Flip to `false` only once you trust what it's doing, and only against the paper account.

## Tests

```bash
uv run pytest
uv run ruff check .
```
