"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/** Runs one full pipeline cycle on demand. When the market is closed the backend
 *  analyzes the last close and records decisions, but places no orders. */
export function RunCycleButton({ onDone }: { onDone: () => void }) {
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setStatus("Running all agents… usually 30–60s.");
    try {
      const result = await api.runCycle();
      const time = new Date(result.ts).toLocaleTimeString(undefined, { hour12: false });
      setStatus(
        result.orders_enabled
          ? `Done at ${time}. Market open, approved orders were submitted.`
          : `Done at ${time}. Market closed: used the last close, no orders placed.`,
      );
      onDone();
    } catch (err) {
      setStatus(`Failed: ${(err as Error).message}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="run-cycle">
      {status && <span className="stat-label">{status}</span>}
      <button
        className="primary-button"
        onClick={run}
        disabled={running}
        title="Run Signal → Risk → Sentiment → Decision for every ticker now. Outside market hours this uses the last close and places no orders."
      >
        {running ? "Running…" : "Run now"}
      </button>
    </div>
  );
}
