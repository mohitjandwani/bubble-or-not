import type { StatePayload } from "../types";
import { zoneColor } from "../constants";
import { cx, flashClass, fmtTime } from "../util";
import { useTweenedNumber } from "../hooks/useAnimatedValue";

export type Tab = "verdict" | "engine";

interface Props {
  state: StatePayload | null;
  offline: boolean;
  changed: Set<string>;
  tab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function TopBar({ state, offline, changed, tab, onTabChange }: Props) {
  const running = state?.status === "running";
  const btiDisplay = useTweenedNumber(state?.bti, 1200);
  return (
    <div className="topbar">
      <div className="wordmark">Bubble or Not</div>
      <div id="topbar-bti" className={cx("mini-gauge", flashClass(changed, "topbar-bti"))}>
        <span className="tnum">{state?.bti == null ? "—" : btiDisplay.toFixed(1)}</span>
        <span className="mini-dot" style={{ background: zoneColor(state?.bti) }} />
      </div>
      <div className="right">
        {offline && <span className="status-chip offline-chip">backend offline — showing last data</span>}
        <span>last updated {fmtTime(state?.updated_at)}</span>
        <span className={cx("status-chip", running && "running")}>
          <span className="pulse-dot" style={{ background: running ? "var(--cyan)" : "var(--green)" }} />
          {state?.status ?? "—"}
        </span>
        <div className="tab-switch" role="tablist" aria-label="Verdict or Engine view">
          <button
            role="tab"
            aria-selected={tab === "verdict"}
            className={cx(tab === "verdict" && "active")}
            onClick={() => onTabChange("verdict")}
          >
            Verdict
          </button>
          <button
            role="tab"
            aria-selected={tab === "engine"}
            className={cx(tab === "engine" && "active")}
            onClick={() => onTabChange("engine")}
          >
            Engine
          </button>
        </div>
      </div>
    </div>
  );
}
