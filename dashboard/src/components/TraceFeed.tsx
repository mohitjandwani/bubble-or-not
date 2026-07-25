import type { RunEvent } from "../types";
import { cx } from "../util";

function fmtTs(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Full run_events feed for the Engine tab — mono table, newest first,
 * run.completed rows highlighted. Polled independently of run status. */
export default function TraceFeed({ events }: { events: RunEvent[] }) {
  const rows = [...events].reverse();
  return (
    <div className="panel trace-feed">
      {rows.length === 0 ? (
        <div className="trace-empty">No events yet — waiting for a run.</div>
      ) : (
        <table className="trace-table">
          <thead>
            <tr>
              <th>ts</th>
              <th>event</th>
              <th>factor</th>
              <th>probe</th>
              <th>endpoint</th>
              <th>cost</th>
              <th>cache</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className={cx(e.event_type === "run.completed" && "trace-complete")}>
                <td className="tnum">{fmtTs(e.ts)}</td>
                <td>{e.event_type}</td>
                <td>{e.factor ?? "—"}</td>
                <td className="tnum">{e.probe_id ?? "—"}</td>
                <td>{e.endpoint ?? "—"}</td>
                <td className="tnum">{e.cost != null ? `$${e.cost.toFixed(3)}` : "—"}</td>
                <td>{e.cache_hit ? "✓" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
