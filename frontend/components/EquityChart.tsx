import type { PortfolioPoint } from "@/lib/types";

const WIDTH = 560;
const HEIGHT = 140;
const PADDING = 8;

/** Minimal hand-rolled SVG sparkline — no charting dependency for one line. */
export function EquityChart({ points }: { points: PortfolioPoint[] }) {
  if (points.length < 2) {
    return <div className="stat-label">Not enough history yet.</div>;
  }

  const equities = points.map((p) => p.equity);
  const min = Math.min(...equities);
  const max = Math.max(...equities);
  const range = max - min || 1;

  const path = points
    .map((point, index) => {
      const x = PADDING + (index / (points.length - 1)) * (WIDTH - 2 * PADDING);
      const y = HEIGHT - PADDING - ((point.equity - min) / range) * (HEIGHT - 2 * PADDING);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const last = points[points.length - 1];
  const first = points[0];
  const up = last.equity >= first.equity;

  return (
    <svg width="100%" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
      <path d={path} fill="none" stroke={up ? "#3ecf8e" : "#f2545b"} strokeWidth={2} />
    </svg>
  );
}
