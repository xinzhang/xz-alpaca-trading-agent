import type { LogEntry } from "@/lib/types";

export function LiveLogFeed({ logs }: { logs: LogEntry[] }) {
  if (logs.length === 0) {
    return <div className="stat-label">No agent activity yet.</div>;
  }

  return (
    <div className="log-feed">
      {logs.map((log, index) => (
        <div className="log-line" key={`${log.ts}-${index}`}>
          <span>{new Date(log.ts).toLocaleTimeString()}</span>
          <span className="node">{log.node}</span>
          <span className="ticker">{log.ticker ?? ""}</span>
          <span>{log.message}</span>
        </div>
      ))}
    </div>
  );
}
