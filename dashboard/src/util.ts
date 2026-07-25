export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function flashClass(changed: Set<string>, id: string): string {
  return changed.has(id) ? "changed" : "";
}

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** Coarse relative-time label ("3m ago", "just now") for the Engine tab's
 * per-probe last-call stats line. */
export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const deltaS = (Date.now() - d.getTime()) / 1000;
  if (deltaS < 10) return "just now";
  if (deltaS < 60) return `${Math.floor(deltaS)}s ago`;
  if (deltaS < 3600) return `${Math.floor(deltaS / 60)}m ago`;
  if (deltaS < 86400) return `${Math.floor(deltaS / 3600)}h ago`;
  return `${Math.floor(deltaS / 86400)}d ago`;
}

/** Scrolls an element into view and gives it one flash pulse — used by every
 * "click an anchor, jump to the evidence row" interaction (A2 dots, hero pins,
 * radar vertices). */
export function scrollToAndFlash(id: string): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("changed");
  window.setTimeout(() => el.classList.remove("changed"), 1300);
}
