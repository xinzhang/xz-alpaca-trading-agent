import type { Account, Decision, Health, LogEntry, PortfolioPoint, Position } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => getJson<Health>("/health"),
  account: () => getJson<Account>("/api/account"),
  positions: () => getJson<Position[]>("/api/positions"),
  decisions: (limit = 50) => getJson<Decision[]>(`/api/decisions?limit=${limit}`),
  logs: (limit = 100) => getJson<LogEntry[]>(`/api/logs?limit=${limit}`),
  portfolioHistory: (limit = 200) =>
    getJson<PortfolioPoint[]>(`/api/portfolio_history?limit=${limit}`),
};

export function wsUrl(): string {
  const base = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
  return `${base}/ws`;
}
