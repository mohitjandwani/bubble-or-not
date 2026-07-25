import { useEffect, useRef, useState } from "react";
import { fetchEngine, fetchEvents } from "../api";
import type { EnginePayload, RunEvent } from "../types";

/** One-shot fetch of the probe registry + live balance for the Engine tab.
 * Refetches if the tab is left and re-entered (component remounts). */
export function useEngineData(): { engine: EnginePayload | null; error: boolean } {
  const [engine, setEngine] = useState<EnginePayload | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchEngine()
      .then((data) => {
        if (!cancelled) {
          setEngine(data);
          setError(false);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { engine, error };
}

const TRACE_POLL_MS = 5000;
const TRACE_MAX = 40;

/** Full run_events feed, polled every 5s for as long as the Engine tab is
 * mounted — independent of run status, unlike the Verdict tab's ticker. */
export function useEngineTrace(): RunEvent[] {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const lastIdRef = useRef(0);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      if (stopped) return;
      try {
        const rows = await fetchEvents(lastIdRef.current);
        if (rows.length > 0) {
          lastIdRef.current = Math.max(lastIdRef.current, ...rows.map((r) => r.id));
          setEvents((prev) => [...prev, ...rows].slice(-TRACE_MAX));
        }
      } catch {
        // trace feed is cosmetic — skip a beat and try again next tick.
      } finally {
        if (!stopped) timer = setTimeout(poll, TRACE_POLL_MS);
      }
    };

    poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return events;
}
