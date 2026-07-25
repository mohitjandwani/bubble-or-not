import { useEffect, useRef, useState } from "react";
import { cx } from "../util";

/** Presentational only: adds an `is-visible` class the first time the wrapper
 * reaches the viewport, so CSS can fade + rise its contents. `delay` staggers
 * siblings. Layout-neutral — the wrapper is a plain block box.
 *
 * Deliberately position-based rather than IntersectionObserver-based. An
 * observer only fires on boundary crossings, so a jump-scroll (the signature
 * dots in Section A call scrollIntoView on a row deep in Section C) can sail
 * past a section without ever triggering it, leaving it stuck at opacity 0.
 * Checking "is it in view, or already behind us?" has no such hole. */
export default function Reveal({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || shown) return;

    let frame: number | null = null;

    const reached = () => {
      const r = el.getBoundingClientRect();
      return r.top < window.innerHeight * 0.98 || r.bottom <= 0;
    };

    const settle = () => {
      frame = null;
      if (reached()) {
        setShown(true);
        teardown();
      }
    };

    const onScroll = () => {
      if (frame == null) frame = requestAnimationFrame(settle);
    };

    const teardown = () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame != null) cancelAnimationFrame(frame);
    };

    if (reached()) {
      setShown(true);
      return;
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return teardown;
  }, [shown]);

  return (
    <div ref={ref} className={cx("reveal", shown && "is-visible")} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}
