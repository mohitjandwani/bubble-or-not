import type { RegistryEdge } from "../types";
import { cx } from "../util";

function fmtAmount(m: number | null | undefined): string {
  if (m == null) return "—";
  return `$${(m / 1000).toFixed(2)}B`;
}

function statusLabel(status: RegistryEdge["status"]): string {
  return status.replace("_", " ");
}

/** Compact financing-flow registry table for the F3 drawer: from -> to,
 * archetype, amount, date, verification status, source. */
export default function EdgesRegistry({ edges }: { edges: RegistryEdge[] }) {
  if (edges.length === 0) return null;
  return (
    <table className="edges-table">
      <thead>
        <tr>
          <th>From</th>
          <th>To</th>
          <th>Type</th>
          <th>Amount</th>
          <th>Date</th>
          <th>Status</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {edges.map((e) => (
          <tr key={e.edge_id} className={cx(e.status === "contradicted" && "contradicted")}>
            <td>{e.from_entity}</td>
            <td>{e.to_entity}</td>
            <td>
              <span className="archetype-chip">{e.archetype}</span>
            </td>
            <td className="tnum">{fmtAmount(e.amount_usd_m)}</td>
            <td className="tnum">{e.announced_date ?? "—"}</td>
            <td>
              <span className={cx("status-pill", e.status)} title={e.note ?? undefined}>
                {statusLabel(e.status)}
              </span>
            </td>
            <td>
              {e.seed_source_url && (
                <a className="source-chip" href={e.seed_source_url} target="_blank" rel="noreferrer">
                  ↗
                </a>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
