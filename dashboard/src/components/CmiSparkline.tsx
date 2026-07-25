import type { SeriesPoint } from "../types";

const W = 150;
const H = 34;

function line(series: SeriesPoint[]): { pts: string; zeroY: number } {
  if (series.length < 2) return { pts: "", zeroY: H / 2 };
  const vals = series.map((p) => p.v);
  const min = Math.min(...vals, 0);
  const max = Math.max(...vals, 0);
  const span = max - min || 1;
  const zeroY = H - ((0 - min) / span) * H;
  const pts = series
    .map((p, i) => {
      const x = (i / (series.length - 1)) * W;
      const y = H - ((p.v - min) / span) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return { pts, zeroY };
}

/** F3 group-header exhibit: two-line CMI sparkline (S1 weekly, S2 monthly) plus
 * the "canary before avalanche" callout when stage1 has already gone negative
 * while stage2 hasn't caught up yet. */
export default function CmiSparkline({
  stage1,
  stage2,
  prebreak,
}: {
  stage1: SeriesPoint[];
  stage2: SeriesPoint[];
  prebreak: boolean;
}) {
  const s1 = line(stage1);
  const s2 = line(stage2);
  return (
    <div className="cmi-spark">
      <div className="cmi-spark-row">
        <span className="cmi-spark-label">S1 wk</span>
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
          <line x1={0} x2={W} y1={s1.zeroY} y2={s1.zeroY} stroke="var(--border)" strokeDasharray="2 2" />
          {s1.pts && <polyline points={s1.pts} fill="none" stroke="var(--cyan)" strokeWidth={1.5} />}
        </svg>
      </div>
      <div className="cmi-spark-row">
        <span className="cmi-spark-label">S2 mo</span>
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
          <line x1={0} x2={W} y1={s2.zeroY} y2={s2.zeroY} stroke="var(--border)" strokeDasharray="2 2" />
          {s2.pts && <polyline points={s2.pts} fill="none" stroke="var(--amber)" strokeWidth={1.5} />}
        </svg>
      </div>
      {prebreak && (
        <span className="tip-wrap canary-chip" data-tip="Stage-1 usage churn has already turned negative while Stage-2 (capex/build-out) hasn't caught up — historically the lead indicator before a broader break.">
          ⚠ canary before avalanche
        </span>
      )}
    </div>
  );
}
