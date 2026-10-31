import type { Decision } from "@/lib/types";

function actionPillClass(action: Decision["action"]): string {
  return { BUY: "pill buy", SELL: "pill sell", HOLD: "pill hold" }[action];
}

/** Whether an order actually went out. HOLDs never place one, so they get no marker. */
function ExecutionMarker({ decision }: { decision: Decision }) {
  if (decision.action === "HOLD") return null;
  const label = decision.executed
    ? "Executed: order submitted"
    : decision.risk_approved
      ? "Not executed: approved, but no order placed (e.g. market closed or nothing to trade)"
      : "Not executed: blocked by risk rules";
  return (
    <span
      className={`exec-marker ${decision.executed ? "executed" : "not-executed"}`}
      title={label}
      aria-label={label}
      role="img"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        {decision.executed ? <path d="M7.5 12.5l3 3 6-6.5" /> : <path d="M8 8l8 8M16 8l-8 8" />}
      </svg>
    </span>
  );
}

export function DecisionsTable({ decisions }: { decisions: Decision[] }) {
  if (decisions.length === 0) {
    return <div className="stat-label">No decisions logged yet — waiting on the first cycle.</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Ticker</th>
          <th>Action</th>
          <th>Confidence</th>
          <th>Risk</th>
          <th>Rationale</th>
        </tr>
      </thead>
      <tbody>
        {decisions.map((decision, index) => (
          <tr key={`${decision.ticker}-${decision.ts}-${index}`}>
            <td style={{ whiteSpace: "nowrap" }}>
              <div className="stat-label">
                {new Date(decision.ts).toLocaleDateString(undefined, {
                  day: "2-digit", month: "short", year: "numeric",
                })}
              </div>
              <div>{new Date(decision.ts).toLocaleTimeString(undefined, { hour12: false })}</div>
            </td>
            <td>{decision.ticker}</td>
            <td>
              <span className={actionPillClass(decision.action)}>{decision.action}</span>
            </td>
            <td>{(decision.confidence * 100).toFixed(0)}%</td>
            <td style={{ whiteSpace: "nowrap" }}>
              <span className={`pill ${decision.risk_approved ? "approved" : "blocked"}`}>
                {decision.risk_approved ? "approved" : "blocked"}
              </span>
              <ExecutionMarker decision={decision} />
            </td>
            <td title={decision.risk_reason ?? undefined}>{decision.rationale}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
