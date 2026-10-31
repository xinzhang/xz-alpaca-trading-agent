export type Action = "BUY" | "SELL" | "HOLD";
export type SentimentLabel = "bullish" | "bearish" | "neutral" | "insufficient_news";

export interface Account {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
}

export interface Position {
  ticker: string;
  qty: number;
  market_value: number;
  avg_entry_price: number;
  unrealized_pl: number;
}

export interface Decision {
  ts: string;
  ticker: string;
  action: Action;
  confidence: number;
  rationale: string;
  risk_approved: boolean;
  risk_reason: string | null;
  executed: boolean;
}

export interface LogEntry {
  ts: string;
  node: string;
  ticker: string | null;
  message: string;
  payload: Record<string, unknown>;
}

export interface PortfolioPoint {
  ts: string;
  equity: number;
  peak_equity: number;
  drawdown_pct: number;
}

export interface RunCycleResult {
  ts: string;
  market_open: boolean;
  orders_enabled: boolean;
  tickers: Record<string, unknown>[];
}

export interface Health {
  status: string;
  dry_run: boolean;
  tickers: string[];
}

export interface LiveEvent {
  type: "agent_log" | "cycle_complete";
  payload: Record<string, unknown>;
}

export interface AnalysisResult {
  symbol: string;
  ts: string;
  signal: {
    bar_count: number;
    technical: {
      last_price: number;
      rsi_14: number | null;
      sma_20: number | null;
      ema_20: number | null;
      bollinger_upper: number | null;
      bollinger_lower: number | null;
    };
    observations: string[];
  };
  risk: {
    equity: number;
    buying_power: number;
    drawdown_pct: number;
    trading_halted: boolean;
    halt_reason: string | null;
    max_position_notional: number;
    remaining_exposure: number;
    position: Omit<Position, "ticker"> & { symbol: string } | null;
    observations: string[];
  };
  sentiment: {
    label: SentimentLabel;
    score: number;
    rationale: string | null;
    headlines: string[];
    articles: { title: string; url: string; published_at: string | null }[];
  };
  decision: {
    action: Action;
    confidence: number;
    rationale: string;
    target_notional: number | null;
    prompt: string;
  };
  risk_check: {
    approved: boolean;
    reason: string | null;
    approved_notional: number | null;
    would_trade: boolean;
  };
  summary: {
    headline: string;
    summary: string;
    bull_case: string[];
    bear_case: string[];
    key_risks: string[];
    what_would_change_the_call: string[];
  };
}
