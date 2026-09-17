import type { Decision } from "@/lib/types";

function actionPillClass(action: Decision["action"]): string {
  return { BUY: "pill buy", SELL: "pill sell", HOLD: "pill hold" }[action];
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
            <td>{new Date(decision.ts).toLocaleTimeString()}</td>
            <td>{decision.ticker}</td>
            <td>
              <span className={actionPillClass(decision.action)}>{decision.action}</span>
            </td>
            <td>{(decision.confidence * 100).toFixed(0)}%</td>
            <td>
              <span className={`pill ${decision.risk_approved ? "approved" : "blocked"}`}>
                {decision.risk_approved ? "approved" : "blocked"}
              </span>
            </td>
            <td title={decision.risk_reason ?? undefined}>{decision.rationale}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
