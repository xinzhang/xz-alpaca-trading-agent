import type { Position } from "@/lib/types";

export function PositionsTable({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return <div className="stat-label">No open positions.</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Qty</th>
          <th>Market value</th>
          <th>Avg entry</th>
          <th>Unrealized P/L</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((position) => (
          <tr key={position.ticker}>
            <td>{position.ticker}</td>
            <td>{position.qty}</td>
            <td>${position.market_value.toFixed(2)}</td>
            <td>${position.avg_entry_price.toFixed(2)}</td>
            <td className={position.unrealized_pl >= 0 ? "positive" : "negative"}>
              ${position.unrealized_pl.toFixed(2)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
