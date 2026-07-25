import type { EnginePayload, Evidence, Factor, RunEvent, StatePayload } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return (await res.json()) as T;
}

export function fetchState(): Promise<StatePayload> {
  return getJson<StatePayload>("/state");
}

export function fetchEngine(): Promise<EnginePayload> {
  return getJson<EnginePayload>("/engine");
}

export function fetchEvents(sinceId: number | null): Promise<RunEvent[]> {
  // Backend envelope: { events: RunEvent[], last_id: number }
  return getJson<{ events: RunEvent[]; last_id: number }>(
    `/events?since=${sinceId ?? 0}`,
  ).then((r) => r.events);
}

export function fetchEvidence(factor: Factor): Promise<Evidence[]> {
  return getJson<Evidence[]>(`/evidence/${factor}`);
}

export function fetchFixtureState(): Promise<StatePayload> {
  return getJson<StatePayload>("/fixtures/state.json");
}

let fixtureEvidenceCache: Evidence[] | null = null;

export async function fetchFixtureEvidenceAll(): Promise<Evidence[]> {
  if (!fixtureEvidenceCache) {
    fixtureEvidenceCache = await getJson<Evidence[]>("/fixtures/evidence.json");
  }
  return fixtureEvidenceCache;
}

export async function fetchFixtureEvidenceForFactor(factor: Factor): Promise<Evidence[]> {
  const all = await fetchFixtureEvidenceAll();
  return all.filter((e) => e.factor === factor);
}

/** Try the live endpoint first; fall back to the bundled fixture so the
 * evidence drawer still works when the backend is offline. */
export async function fetchEvidenceWithFallback(factor: Factor): Promise<Evidence[]> {
  try {
    return await fetchEvidence(factor);
  } catch {
    return fetchFixtureEvidenceForFactor(factor);
  }
}
