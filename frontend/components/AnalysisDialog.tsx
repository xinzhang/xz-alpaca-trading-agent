"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { Action, AnalysisResult } from "@/lib/types";

const STEPS = ["Signal", "Risk", "Sentiment", "Decision", "Risk gate", "Summary"];

const usd = (value: number | null | undefined) =>
  value == null ? "—" : `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
const num = (value: number | null | undefined, digits = 2) =>
  value == null ? "—" : value.toFixed(digits);

function actionPill(action: Action) {
  return <span className={`pill ${action.toLowerCase()}`}>{action}</span>;
}

function Section({ step, title, children }: { step: number; title: string; children: ReactNode }) {
  return (
    <section className="analysis-section">
      <h3>
        <span className="step-num">{step}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Metrics({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="metrics">
      {items.map(([label, value]) => (
        <div key={label}>
          <div className="stat-label">{label}</div>
          <div>{value}</div>
        </div>
      ))}
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) return <div className="stat-label">None.</div>;
  return (
    <ul className="bullets">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

function AnalysisReport({ result }: { result: AnalysisResult }) {
  const { signal, risk, sentiment, decision, risk_check: gate, summary } = result;
  const t = signal.technical;

  return (
    <div className="analysis-report">
      <div className="verdict">
        <div className="verdict-line">
          <strong>{result.symbol}</strong>
          {actionPill(decision.action)}
          <span>{(decision.confidence * 100).toFixed(0)}% confidence</span>
          <span className={`pill ${gate.would_trade ? "approved" : "blocked"}`}>
            {gate.would_trade ? `would trade ${usd(gate.approved_notional)}` : "no trade"}
          </span>
        </div>
        <div>{summary.headline}</div>
        <div className="stat-label">
          Analysis only — no order was placed. {new Date(result.ts).toLocaleString()}
        </div>
      </div>

      <Section step={1} title="Signal agent — technicals">
        <Metrics
          items={[
            ["Last price", usd(t.last_price)],
            ["RSI(14)", num(t.rsi_14, 1)],
            ["SMA(20)", usd(t.sma_20)],
            ["EMA(20)", usd(t.ema_20)],
            ["Bollinger", `${usd(t.bollinger_lower)} – ${usd(t.bollinger_upper)}`],
            ["Bars", `${signal.bar_count} × 1-min`],
          ]}
        />
        <Bullets items={signal.observations} />
      </Section>

      <Section step={2} title="Risk agent — account budget">
        <Metrics
          items={[
            ["Equity", usd(risk.equity)],
            ["Drawdown", `${(risk.drawdown_pct * 100).toFixed(2)}%`],
            ["Position cap", usd(risk.max_position_notional)],
            ["Exposure left", usd(risk.remaining_exposure)],
            ["Current position", risk.position ? usd(risk.position.market_value) : "none"],
            [
              "Status",
              <span key="s" className={`pill ${risk.trading_halted ? "blocked" : "approved"}`}>
                {risk.trading_halted ? "halted" : "trading allowed"}
              </span>,
            ],
          ]}
        />
        <Bullets items={risk.observations} />
      </Section>

      <Section step={3} title="Sentiment agent — news">
        <Metrics
          items={[
            ["Label", sentiment.label.replace("_", " ")],
            ["Score", num(sentiment.score)],
            ["Articles", String(sentiment.articles.length)],
          ]}
        />
        {sentiment.rationale && <p>{sentiment.rationale}</p>}
        <div className="stat-label">Articles the model read (last ~48h, newest first)</div>
        {sentiment.articles.length === 0 ? (
          <div className="stat-label">None.</div>
        ) : (
          <ul className="bullets">
            {sentiment.articles.map((article) => (
              <li key={article.url}>
                <a href={article.url} target="_blank" rel="noreferrer">
                  {article.title}
                </a>
                {article.published_at && (
                  <span className="stat-label"> · {article.published_at}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section step={4} title="Decision agent — proposal">
        <Metrics
          items={[
            ["Action", actionPill(decision.action)],
            ["Confidence", `${(decision.confidence * 100).toFixed(0)}%`],
            ["Target position", usd(decision.target_notional)],
          ]}
        />
        <p>{decision.rationale}</p>
        <details>
          <summary className="stat-label">Prompt sent to the model</summary>
          <pre>{decision.prompt}</pre>
        </details>
      </Section>

      <Section step={5} title="Risk gate — hard-coded rules">
        <Metrics
          items={[
            [
              "Verdict",
              <span key="v" className={`pill ${gate.approved ? "approved" : "blocked"}`}>
                {gate.approved ? "approved" : "blocked"}
              </span>,
            ],
            ["Order size", usd(gate.approved_notional)],
            [
              "Reason",
              gate.reason ?? (decision.action === "HOLD" ? "HOLD — no order needed" : "—"),
            ],
          ]}
        />
      </Section>

      <Section step={6} title="Summary">
        <p>{summary.summary}</p>
        <div className="summary-grid">
          <div>
            <div className="stat-label positive">Bull case</div>
            <Bullets items={summary.bull_case} />
          </div>
          <div>
            <div className="stat-label negative">Bear case</div>
            <Bullets items={summary.bear_case} />
          </div>
          <div>
            <div className="stat-label">Key risks</div>
            <Bullets items={summary.key_risks} />
          </div>
          <div>
            <div className="stat-label">What would change the call</div>
            <Bullets items={summary.what_would_change_the_call} />
          </div>
        </div>
      </Section>
    </div>
  );
}

export function AnalysisDialog({
  onClose,
  suggestions,
}: {
  onClose: () => void;
  suggestions: string[];
}) {
  const [symbol, setSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus only on open: re-focusing on every re-render (the dashboard polls) would
  // keep clearing any text the user has selected in the report.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const run = async (target: string) => {
    const cleaned = target.trim().toUpperCase();
    if (!cleaned || loading) return;
    setSymbol(cleaned);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.analyze(cleaned));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void run(symbol);
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Analyze a symbol"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Analyze a symbol</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <form className="analyze-form" onSubmit={onSubmit}>
          <input
            ref={inputRef}
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
            placeholder="Symbol, e.g. AAPL"
            maxLength={10}
            disabled={loading}
          />
          <button className="primary-button" type="submit" disabled={loading || !symbol.trim()}>
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </form>
        {suggestions.length > 0 && (
          <div className="chips">
            {suggestions.map((ticker) => (
              <button key={ticker} className="chip" onClick={() => run(ticker)} disabled={loading}>
                {ticker}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="stat-label analysis-progress">
            Running {STEPS.join(" → ")} for {symbol}… this usually takes 10–30s.
          </div>
        )}
        {error && <div className="negative analysis-progress">{error}</div>}
        {result && <AnalysisReport result={result} />}
      </div>
    </div>
  );
}
