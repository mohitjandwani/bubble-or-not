import { useEffect, useRef, useState } from "react";

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/** Tweens a single number from its previous value to `target` over `durationMs`
 * whenever `target` changes. Used for the BTI count-up and the gauge needle sweep. */
export function useTweenedNumber(target: number | null | undefined, durationMs = 1200): number {
  const [display, setDisplay] = useState(target ?? 0);
  const fromRef = useRef(target ?? 0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const to = target ?? 0;
    const from = fromRef.current;
    if (from === to) {
      setDisplay(to);
      return;
    }
    const start = performance.now();
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOutCubic(t);
      setDisplay(from + (to - from) * eased);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);

  return display;
}

/** Same idea, but tweens every element of a fixed-length numeric array in lockstep —
 * used for the radar polygon morph. */
export function useTweenedArray(target: number[], durationMs = 400): number[] {
  const [display, setDisplay] = useState(target);
  const fromRef = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    if (from.length !== target.length || from.every((v, i) => v === target[i])) {
      setDisplay(target);
      fromRef.current = target;
      return;
    }
    const start = performance.now();
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOutCubic(t);
      setDisplay(from.map((v, i) => v + (target[i] - v) * eased));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(target), durationMs]);

  return display;
}

/** Fades `value` out, swaps to the new value, fades it back in. Returns the value
 * to render plus whether it's currently in the "visible" (faded-in) phase, so the
 * caller can drive a CSS opacity transition. */
export function useCrossfade<T>(value: T, durationMs = 250): { display: T; visible: boolean } {
  const [display, setDisplay] = useState(value);
  const [visible, setVisible] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (value === display) return;
    setVisible(false);
    timeoutRef.current = setTimeout(() => {
      setDisplay(value);
      setVisible(true);
    }, durationMs);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs]);

  return { display, visible };
}
