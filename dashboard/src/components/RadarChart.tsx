import { FACTOR_NAMES, FACTOR_ORDER } from "../constants";
import type { FactorResult } from "../types";

const CX = 150;
const CY = 150;
const R = 110;

function vertex(i: number, value: number) {
  const angle = ((-90 + i * 72) * Math.PI) / 180;
  const r = (Math.max(0, Math.min(100, value)) / 100) * R;
  return { x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) };
}

function labelPos(i: number) {
  const angle = ((-90 + i * 72) * Math.PI) / 180;
  return { x: CX + (R + 26) * Math.cos(angle), y: CY + (R + 26) * Math.sin(angle) };
}

function scrollToFactor(factor: string) {
  document.getElementById(`factor-group-${factor}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function RadarChart({
  scores,
  thresholds,
}: {
  scores: Record<string, FactorResult | undefined>;
  thresholds: Record<string, number>;
}) {
  const todayPts = FACTOR_ORDER.map((f, i) => vertex(i, scores[f]?.score ?? 0));
  const dangerPts = FACTOR_ORDER.map((f, i) => vertex(i, thresholds[f] ?? 0));
  const toStr = (pts: { x: number; y: number }[]) => pts.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox="0 0 300 320" width="100%" height={320}>
      <polygon points={toStr(dangerPts)} fill="none" stroke="var(--dim)" strokeDasharray="4 4" strokeWidth={1.5} />
      <polygon points={toStr(todayPts)} fill="var(--cyan)" fillOpacity={0.25} stroke="var(--cyan)" strokeWidth={2} />
      {todayPts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="var(--cyan)" />
      ))}
      {FACTOR_ORDER.map((f, i) => {
        const lp = labelPos(i);
        return (
          <text
            key={f}
            x={lp.x}
            y={lp.y}
            fontSize={11}
            fill="var(--dim)"
            textAnchor="middle"
            style={{ cursor: "pointer" }}
            onClick={() => scrollToFactor(f)}
          >
            {FACTOR_NAMES[f]} · {scores[f]?.score?.toFixed(0) ?? "—"}
          </text>
        );
      })}
    </svg>
  );
}
