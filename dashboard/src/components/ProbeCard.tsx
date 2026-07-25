import { useState } from "react";
import type { EngineProbe, ProbePattern, ProbeStat } from "../types";
import { cx, fmtRelativeTime } from "../util";

const PATTERN_INFO: Record<ProbePattern, { label: string; color: string }> = {
  A: { label: "A · typed + domain-locked", color: "var(--cyan)" },
  B: { label: "B · finance index → extract()", color: "var(--amber)" },
  SEARCH: { label: "SEARCH", color: "var(--text)" },
  QUANT: { label: "QUANT · no LLM", color: "var(--green)" },
};

function fmtParamValue(v: unknown): string {
  if (v == null) return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function fmtElapsed(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** One probe in the API usage map — collapsed shows the auditable shape at a
 * glance (pattern/endpoint/effort/cadence/cost); expanded shows the literal
 * query text, params, typed output schema, and local rubric, verbatim. */
export default function ProbeCard({ probe, stat }: { probe: EngineProbe; stat?: ProbeStat }) {
  const [open, setOpen] = useState(false);
  const pattern = PATTERN_INFO[probe.pattern];
  const paramEntries = Object.entries(probe.params ?? {});

  return (
    <div className="probe-card">
      <div
        className="probe-row"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((o) => !o);
          }
        }}
      >
        <span className={cx("probe-caret", open && "open")}>▸</span>
        <span className="probe-id tnum">{probe.probe_id}</span>
        <span className="tip-wrap pattern-chip" data-tip={pattern.label} style={{ color: pattern.color, borderColor: pattern.color }}>
          {probe.pattern}
        </span>
        <span className="engine-chip">{probe.endpoint}</span>
        {probe.effort && <span className="engine-chip">{probe.effort}</span>}
        <span className="engine-chip">{probe.cadence}</span>
        <span className="probe-cost tnum">${probe.cost_est_usd.toFixed(3)}</span>
      </div>
      <div className="probe-why">{probe.why_youcom}</div>

      {open && (
        <div className="probe-detail">
          {probe.query ? (
            <div className="probe-query">{probe.query}</div>
          ) : (
            <div className="probe-query probe-query-empty">no LLM query — pure data feed</div>
          )}

          {paramEntries.length > 0 && (
            <div className="probe-params">
              {paramEntries.map(([k, v]) => (
                <span key={k} className="param-chip">
                  <span className="param-key">{k}</span>
                  <span className="param-sep">:</span>
                  <span className="param-value tnum">{fmtParamValue(v)}</span>
                </span>
              ))}
            </div>
          )}

          {probe.output_schema && (
            <details className="probe-schema">
              <summary>typed output schema ▸</summary>
              <pre>{probe.output_schema}</pre>
            </details>
          )}

          {probe.local_llm && (
            <details className="probe-schema">
              <summary>local Haiku rubric ▸</summary>
              <pre>{probe.local_llm}</pre>
            </details>
          )}

          {stat && (
            <div className="probe-stat-line tnum">
              last: ${(stat.last_cost ?? 0).toFixed(3)} · {fmtElapsed(stat.last_elapsed_ms)} ·{" "}
              {stat.cache_hit ? "cache hit ✓" : "fresh call"} · {fmtRelativeTime(stat.last_ts)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
