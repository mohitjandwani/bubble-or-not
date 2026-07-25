import type { ReactNode } from "react";

/** Floating tooltip positioned inside a `position: relative` chart wrapper.
 * `leftPct` is 0-100 (percent of wrapper width), `topPx` is pixels (charts here
 * render at a fixed pixel height, so vertical position is 1:1 with SVG space). */
export default function HoverTip({
  leftPct,
  topPx,
  children,
}: {
  leftPct: number;
  topPx: number;
  children: ReactNode;
}) {
  return (
    <div className="hover-tip" style={{ left: `${leftPct}%`, top: topPx }}>
      {children}
    </div>
  );
}
