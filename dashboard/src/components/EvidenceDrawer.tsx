import { useEffect, useState } from "react";
import { fetchEvidenceWithFallback } from "../api";
import type { Evidence, SignatureState } from "../types";
import { confidenceColor } from "../constants";

function provenanceLine(p: Record<string, unknown>): string {
  const parts: string[] = [];
  if (typeof p.endpoint === "string") parts.push(p.endpoint);
  if (typeof p.effort === "string") parts.push(p.effort);
  if (typeof p.params === "string") parts.push(p.params);
  if (typeof p.cost_usd === "number") parts.push(`$${p.cost_usd.toFixed(2)}`);
  if (typeof p.elapsed_s === "number") parts.push(`${p.elapsed_s.toFixed(0)}s`);
  return parts.join(" · ");
}

export default function EvidenceDrawer({ signature }: { signature: SignatureState }) {
  const [rows, setRows] = useState<Evidence[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEvidenceWithFallback(signature.factor).then((data) => {
      if (!cancelled) setRows(data);
    });
    return () => {
      cancelled = true;
    };
  }, [signature.factor]);

  if (rows === null) {
    return <div className="evidence-drawer">Loading evidence…</div>;
  }

  const probeId = `probe-${signature.signature_id}`;
  const own = rows.filter((r) => r.probe_id === probeId);
  const other = rows.filter((r) => r.probe_id !== probeId);

  const byMetric = new Map<string, Set<number>>();
  own.forEach((r) => {
    if (r.value == null) return;
    const set = byMetric.get(r.metric) ?? new Set<number>();
    set.add(r.value);
    byMetric.set(r.metric, set);
  });
  const hasConflict = [...byMetric.values()].some((s) => s.size > 1);

  const renderRow = (r: Evidence, dimmed: boolean) => (
    <>
      <tr key={r.evidence_id} className={dimmed ? "dimmed" : undefined}>
        <td>{r.metric}</td>
        <td className="tnum">{r.value ?? "—"}</td>
        <td>{r.unit ?? ""}</td>
        <td className="tnum">{r.as_of ?? "—"}</td>
        <td>
          <span
            className="confidence-dot"
            style={{ display: "inline-block", background: confidenceColor(r.confidence) }}
            title={r.confidence}
          />{" "}
          {r.confidence}
        </td>
        <td>
          {r.source_url && (
            <a className="source-chip" href={r.source_url} target="_blank" rel="noreferrer">
              source
            </a>
          )}
        </td>
      </tr>
      {r.quote && (
        <tr key={`${r.evidence_id}-quote`} className={dimmed ? "dimmed" : undefined}>
          <td colSpan={6}>
            <div className="ev-quote">&ldquo;{r.quote}&rdquo;</div>
            <div className="provenance-line">{provenanceLine(r.provenance)}</div>
          </td>
        </tr>
      )}
    </>
  );

  return (
    <div className="evidence-drawer">
      {hasConflict && (
        <div className="conflict-banner">⚠ conflicting sources — excluded from score</div>
      )}
      <table className="evidence-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Unit</th>
            <th>As of</th>
            <th>Confidence</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {own.map((r) => renderRow(r, false))}
          {other.map((r) => renderRow(r, true))}
        </tbody>
      </table>
    </div>
  );
}
