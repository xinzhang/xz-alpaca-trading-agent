import type { Account, PortfolioPoint } from "@/lib/types";

function money(value: number): string {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function AccountSummary({
  account,
  latestSnapshot,
}: {
  account: Account | null;
  latestSnapshot: PortfolioPoint | null;
}) {
  const stats = [
    { label: "Equity", value: account ? money(account.equity) : "—" },
    { label: "Cash", value: account ? money(account.cash) : "—" },
    { label: "Buying power", value: account ? money(account.buying_power) : "—" },
    {
      label: "Drawdown from peak",
      value: latestSnapshot ? `${(latestSnapshot.drawdown_pct * 100).toFixed(2)}%` : "—",
      warn: latestSnapshot ? latestSnapshot.drawdown_pct > 0.05 : false,
    },
  ];

  return (
    <div className="grid cols-4">
      {stats.map((stat) => (
        <div className="panel" key={stat.label}>
          <div className={`stat-value ${stat.warn ? "negative" : ""}`}>{stat.value}</div>
          <div className="stat-label">{stat.label}</div>
        </div>
      ))}
    </div>
  );
}
