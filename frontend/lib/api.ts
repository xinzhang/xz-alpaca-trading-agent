import type { Account, AnalysisResult, Decision, Health, LogEntry, PortfolioPoint, Position } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8682";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().then((b) => b.detail).catch(() => null);
    throw new Error(typeof detail === "string" ? detail : `${path} failed: ${response.status}`);
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
  analyze: (symbol: string) => postJson<AnalysisResult>("/api/analyze", { symbol }),
};

export function wsUrl(): string {
  const base = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8682";
  return `${base}/ws`;
}
