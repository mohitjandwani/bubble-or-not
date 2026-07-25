import type { WaterfallBar } from "../types";

const TRACK_W = 220;

function barColor(kind: WaterfallBar["kind"]): string {
  if (kind === "reported") return "var(--dim)";
  if (kind === "deduction") return "var(--red)";
  return "var(--green)";
}

function fmtUsd(v: number): string {
  return `$${v.toFixed(1)}B`;
}

function Bar({ bar, maxVal }: { bar: WaterfallBar; maxVal: number }) {
  const low = bar.value_low ?? 0;
  const high = bar.value_high ?? low;
  const wLow = (Math.min(low, high) / maxVal) * TRACK_W;
  const wHigh = (Math.max(low, high) / maxVal) * TRACK_W;
  const hasRange = high !== low;
  const color = barColor(bar.kind);
  return (
    <div className="wf-row">
      <span className="wf-label" title={bar.note ?? undefined}>
        {bar.label}
      </span>
      <div className="wf-track">
        <div className="wf-fill" style={{ width: `${wHigh}px`, background: color }} />
        {hasRange && (
          <div className="wf-whisker" style={{ left: `${wLow}px`, width: `${Math.max(1, wHigh - wLow)}px` }} />
        )}
      </div>
      <span className="wf-value tnum">{hasRange ? `${fmtUsd(low)}–${fmtUsd(high)}` : fmtUsd(low)}</span>
      {bar.citation_url && (
        <a className="source-chip wf-chip" href={bar.citation_url} target="_blank" rel="noreferrer" title="source">
          ↗
        </a>
      )}
    </div>
  );
}

/** Revenue Quality Waterfall — horizontal bar chart per lab: the reported ARR as
 * a reference bar, deductions with min/max uncertainty whiskers, and the
 * resulting cash-quality band. */
export default function WaterfallChart({
  waterfalls,
  revenueQuality,
}: {
  waterfalls: Record<string, WaterfallBar[]>;
  revenueQuality: Record<string, number | null | undefined>;
}) {
  const labs = Object.keys(waterfalls);
  if (labs.length === 0) return null;
  return (
    <div className="waterfall-grid">
      {labs.map((lab) => {
        const bars = waterfalls[lab];
        const maxVal = Math.max(1, ...bars.map((b) => Math.max(b.value_high ?? 0, b.value_low ?? 0)));
        const rq = revenueQuality[lab];
        return (
          <div key={lab} className="waterfall-col">
            <div className="waterfall-col-header">
              <span className="waterfall-lab-name">{lab}</span>
              {rq != null && <span className="rq-chip tnum">RQ {rq.toFixed(2)}</span>}
            </div>
            {bars.map((b, i) => (
              <Bar key={`${lab}-${i}`} bar={b} maxVal={maxVal} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
