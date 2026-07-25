import { useState } from "react";
import { FACTOR_NAMES, FACTOR_ORDER } from "../constants";
import type { Factor, FactorResult } from "../types";
import { scrollToAndFlash } from "../util";
import { useTweenedArray } from "../hooks/useAnimatedValue";
import HoverTip from "./HoverTip";

const CX = 150;
const CY = 150;
const R = 110;
const VIEW_W = 300;
const VIEW_H = 320;

function vertex(i: number, value: number) {
  const angle = ((-90 + i * 72) * Math.PI) / 180;
  const r = (Math.max(0, Math.min(100, value)) / 100) * R;
  return { x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) };
}

function labelPos(i: number) {
  const angle = ((-90 + i * 72) * Math.PI) / 180;
  return { x: CX + (R + 26) * Math.cos(angle), y: CY + (R + 26) * Math.sin(angle) };
}

export default function RadarChart({
  scores,
  thresholds,
}: {
  scores: Record<string, FactorResult | undefined>;
  thresholds: Record<string, number>;
}) {
  const [hover, setHover] = useState<{ factor: Factor; x: number; y: number } | null>(null);

  const rawToday = FACTOR_ORDER.map((f) => scores[f]?.score ?? 0);
  const rawDanger = FACTOR_ORDER.map((f) => thresholds[f] ?? 0);
  // Morph the polygon shape to its new values over ~400ms on rescore.
  const todayVals = useTweenedArray(rawToday, 400);
  const dangerVals = useTweenedArray(rawDanger, 400);

  const todayPts = todayVals.map((v, i) => vertex(i, v));
  const dangerPts = dangerVals.map((v, i) => vertex(i, v));
  const toStr = (pts: { x: number; y: number }[]) => pts.map((p) => `${p.x},${p.y}`).join(" ");

  const hoverFactor = hover ? scores[hover.factor] : null;
  const hoverScore = hover ? rawToday[FACTOR_ORDER.indexOf(hover.factor)] : 0;
  const hoverThreshold = hover ? rawDanger[FACTOR_ORDER.indexOf(hover.factor)] : 0;
  const hoverBreach = hoverScore - hoverThreshold;

  return (
    <div className="radar-wrap" style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%" height={VIEW_H}>
        <polygon points={toStr(dangerPts)} fill="none" stroke="var(--dim)" strokeDasharray="4 4" strokeWidth={1.5} />
        <polygon points={toStr(todayPts)} fill="var(--cyan)" fillOpacity={0.25} stroke="var(--cyan)" strokeWidth={2} />

        {/* Per-spoke breach: where today exceeds the danger threshold, draw the
            overlap segment (and vertex) in red — instantly visible danger zones. */}
        {FACTOR_ORDER.map((f, i) => {
          const breached = todayVals[i] > dangerVals[i];
          if (!breached) return null;
          const a = dangerPts[i];
          const b = todayPts[i];
          return <line key={`breach-${f}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--red)" strokeWidth={4} strokeLinecap="round" />;
        })}

        {todayPts.map((p, i) => {
          const f = FACTOR_ORDER[i];
          const breached = todayVals[i] > dangerVals[i];
          return (
            <circle
              key={f}
              cx={p.x}
              cy={p.y}
              r={breached ? 4.5 : 3}
              fill={breached ? "var(--red)" : "var(--cyan)"}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover({ factor: f, x: p.x, y: p.y })}
              onMouseLeave={() => setHover(null)}
              onClick={() => scrollToAndFlash(`factor-group-${f}`)}
            />
          );
        })}

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
              onClick={() => scrollToAndFlash(`factor-group-${f}`)}
              onMouseEnter={() => setHover({ factor: f, x: todayPts[i].x, y: todayPts[i].y })}
              onMouseLeave={() => setHover(null)}
            >
              {FACTOR_NAMES[f]} · {scores[f]?.score?.toFixed(0) ?? "—"}
            </text>
          );
        })}
      </svg>

      {hover && (
        <HoverTip leftPct={(hover.x / VIEW_W) * 100} topPx={hover.y}>
          <div className="tip-title">{FACTOR_NAMES[hover.factor]}</div>
          <div className="tnum">
            score {hoverScore.toFixed(0)} · threshold {hoverThreshold.toFixed(0)}
          </div>
          {hoverBreach > 0 ? (
            <div className="tip-breach tnum">breached by +{hoverBreach.toFixed(0)}</div>
          ) : (
            <div className="tnum" style={{ color: "var(--dim)" }}>
              {Math.abs(hoverBreach).toFixed(0)} below threshold
            </div>
          )}
          {hoverFactor?.state && hoverFactor.state !== "ok" && (
            <div style={{ color: "var(--yellow)" }}>{hoverFactor.state}</div>
          )}
        </HoverTip>
      )}
    </div>
  );
}
