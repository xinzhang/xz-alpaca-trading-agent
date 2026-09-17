export type Action = "BUY" | "SELL" | "HOLD";
export type SentimentLabel = "bullish" | "bearish" | "neutral";

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

export interface Health {
  status: string;
  dry_run: boolean;
  tickers: string[];
}

export interface LiveEvent {
  type: "agent_log" | "cycle_complete";
  payload: Record<string, unknown>;
}
