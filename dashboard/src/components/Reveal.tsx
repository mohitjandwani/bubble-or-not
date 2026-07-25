import { useEffect, useRef, useState } from "react";
import { cx } from "../util";

/** Presentational only: adds an `is-visible` class the first time the wrapper
 * scrolls into view, so CSS can fade + rise its contents. `delay` staggers
 * siblings. Layout-neutral — the wrapper is a plain block box. */
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
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.04 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [shown]);

  return (
    <div ref={ref} className={cx("reveal", shown && "is-visible")} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}
