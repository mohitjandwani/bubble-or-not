import type { StatePayload } from "./types";

/** DOM element ids that should get the `.changed` flash on a state transition.
 * Elements register with these same ids (see components) so this stays the
 * single source of truth for "what counts as a change" in Pass 1. */
export function computeChangedIds(prev: StatePayload | null, next: StatePayload): string[] {
  if (!prev) return [];
  const ids: string[] = [];

  if (prev.bti !== next.bti) {
    ids.push("bti-number", "topbar-bti");
  }

  const prevFactors = new Map(prev.factors.map((f) => [f.factor, f]));
  for (const f of next.factors) {
    const p = prevFactors.get(f.factor);
    if (p && p.score !== f.score) {
      ids.push(`factor-bar-${f.factor}`);
    }
  }

  const prevSigs = new Map(prev.signatures.map((s) => [s.signature_id, s]));
  for (const s of next.signatures) {
    const p = prevSigs.get(s.signature_id);
    if (p && p.lamp !== s.lamp) {
      ids.push(s.signature_id, `dot-${s.signature_id}`);
    }
  }

  return ids;
}
