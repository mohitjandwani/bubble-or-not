import { useCallback, useEffect, useRef, useState } from "react";
import { fetchEvents, fetchFixtureState, fetchState } from "../api";
import { computeChangedIds } from "../diff";
import type { RunEvent, StatePayload } from "../types";

const IDLE_POLL_MS = 15000;
const RUNNING_POLL_MS = 2000;
const EVENTS_POLL_MS = 2000;
const FLASH_MS = 1300;

export interface DashboardData {
  state: StatePayload | null;
  offline: boolean;
  usingFixtures: boolean;
  events: RunEvent[];
  changed: Set<string>;
}

export function useDashboardData(): DashboardData {
  const [state, setState] = useState<StatePayload | null>(null);
  const [offline, setOffline] = useState(false);
  const [usingFixtures, setUsingFixtures] = useState(false);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [changed, setChanged] = useState<Set<string>>(new Set());

  const stateRef = useRef<StatePayload | null>(null);
  const stateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastEventIdRef = useRef<number>(0);
  const flashTimeoutsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const stoppedRef = useRef(false);

  const markChanged = useCallback((ids: string[]) => {
    if (ids.length === 0) return;
    setChanged((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.add(id));
      return next;
    });
    ids.forEach((id) => {
      const existing = flashTimeoutsRef.current.get(id);
      if (existing) clearTimeout(existing);
      const t = setTimeout(() => {
        setChanged((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
        flashTimeoutsRef.current.delete(id);
      }, FLASH_MS);
      flashTimeoutsRef.current.set(id, t);
    });
  }, []);

  const scheduleStatePoll = useCallback((delay: number, run: () => Promise<void>) => {
    if (stateTimerRef.current) clearTimeout(stateTimerRef.current);
    stateTimerRef.current = setTimeout(run, delay);
  }, []);

  useEffect(() => {
    stoppedRef.current = false;

    const pollState = async () => {
      if (stoppedRef.current) return;
      try {
        const next = await fetchState();
        setOffline(false);
        setUsingFixtures(false);
        const prev = stateRef.current;
        markChanged(computeChangedIds(prev, next));
        stateRef.current = next;
        setState(next);
      } catch {
        if (stateRef.current === null) {
          // First load failed entirely — fall back to bundled fixtures so the
          // app is usable with no backend running.
          try {
            const fixture = await fetchFixtureState();
            stateRef.current = fixture;
            setState(fixture);
            setUsingFixtures(true);
          } catch {
            // even the fixture failed to load; nothing to render yet.
          }
        }
        setOffline(true);
      } finally {
        const delay = stateRef.current?.status === "running" ? RUNNING_POLL_MS : IDLE_POLL_MS;
        scheduleStatePoll(delay, pollState);
      }
    };

    pollState();

    return () => {
      stoppedRef.current = true;
      if (stateTimerRef.current) clearTimeout(stateTimerRef.current);
      flashTimeoutsRef.current.forEach((t) => clearTimeout(t));
      flashTimeoutsRef.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const running = state?.status === "running";

    const pollEvents = async () => {
      try {
        const rows = await fetchEvents(lastEventIdRef.current);
        if (rows.length > 0) {
          lastEventIdRef.current = Math.max(lastEventIdRef.current, ...rows.map((r) => r.id));
          setEvents((prev) => [...prev, ...rows].slice(-5));
        }
      } catch {
        // events are cosmetic (trace ticker) — silently skip a beat.
      } finally {
        if (state?.status === "running" && !stoppedRef.current) {
          eventsTimerRef.current = setTimeout(pollEvents, EVENTS_POLL_MS);
        }
      }
    };

    if (running) {
      pollEvents();
    } else {
      lastEventIdRef.current = 0;
      setEvents([]);
    }

    return () => {
      if (eventsTimerRef.current) clearTimeout(eventsTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status]);

  return { state, offline, usingFixtures, events, changed };
}
