"use client";

import { useMemo } from "react";
import { api } from "@/lib/api";
import { usePolledData } from "@/lib/usePolledData";
import { useLiveEvents } from "@/lib/useLiveEvents";
import { AccountSummary } from "@/components/AccountSummary";
import { EquityChart } from "@/components/EquityChart";
import { PositionsTable } from "@/components/PositionsTable";
import { DecisionsTable } from "@/components/DecisionsTable";
import { LiveLogFeed } from "@/components/LiveLogFeed";
import type { LogEntry } from "@/lib/types";

export default function DashboardPage() {
  const health = usePolledData(api.health, 30_000);
  const account = usePolledData(api.account, 15_000);
  const positions = usePolledData(api.positions, 15_000);
  const decisions = usePolledData(() => api.decisions(50), 15_000);
  const portfolioHistory = usePolledData(() => api.portfolioHistory(200), 30_000);
  const historicalLogs = usePolledData(() => api.logs(100), 20_000);
  const { connected, events } = useLiveEvents();

  const liveLogs: LogEntry[] = useMemo(
    () =>
      events
        .filter((event) => event.type === "agent_log")
        .map((event) => event.payload as unknown as LogEntry),
    [events],
  );

  const mergedLogs = useMemo(() => {
    const seen = new Set<string>();
    const combined = [...liveLogs, ...(historicalLogs.data ?? [])];
    return combined.filter((log) => {
      const key = `${log.ts}|${log.node}|${log.ticker}|${log.message}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [liveLogs, historicalLogs.data]);

  const latestSnapshot = portfolioHistory.data?.at(-1) ?? null;

  return (
    <main className="page">
      <div className="topbar">
        <div className="title">AlphaDesk Console</div>
        <div style={{ display: "flex", gap: 10 }}>
          {health.data && (
            <span className="badge">{health.data.dry_run ? "DRY RUN" : "LIVE PAPER"}</span>
          )}
          <span className="badge">
            <span className={`dot ${connected ? "on" : "off"}`} />
            {connected ? "live" : "reconnecting…"}
          </span>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <AccountSummary account={account.data} latestSnapshot={latestSnapshot} />
      </div>

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <div className="panel">
          <h2>Equity</h2>
          <EquityChart points={portfolioHistory.data ?? []} />
        </div>
        <div className="panel">
          <h2>Positions</h2>
          <PositionsTable positions={positions.data ?? []} />
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2>Recent decisions</h2>
        <DecisionsTable decisions={decisions.data ?? []} />
      </div>

      <div className="panel">
        <h2>Agent activity</h2>
        <LiveLogFeed logs={mergedLogs} />
      </div>
    </main>
  );
}
