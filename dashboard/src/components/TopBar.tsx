import type { StatePayload } from "../types";
import { zoneColor } from "../constants";
import { cx, flashClass, fmtNum, fmtTime } from "../util";

interface Props {
  state: StatePayload | null;
  offline: boolean;
  changed: Set<string>;
}

export default function TopBar({ state, offline, changed }: Props) {
  const running = state?.status === "running";
  return (
    <div className="topbar">
      <div className="wordmark">Bubble or Not</div>
      <div id="topbar-bti" className={cx("mini-gauge", flashClass(changed, "topbar-bti"))}>
        <span className="tnum">{fmtNum(state?.bti)}</span>
        <span className="mini-dot" style={{ background: zoneColor(state?.bti) }} />
      </div>
      <div className="right">
        {offline && <span className="status-chip offline-chip">backend offline — showing last data</span>}
        <span>last updated {fmtTime(state?.updated_at)}</span>
        <span className={cx("status-chip", running && "running")}>
          <span className="pulse-dot" style={{ background: running ? "var(--cyan)" : "var(--green)" }} />
          {state?.status ?? "—"}
        </span>
      </div>
    </div>
  );
}
