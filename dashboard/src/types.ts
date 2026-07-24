/** Mirrors schema.py exactly. Field names must match the API payloads 1:1. */

export type Factor = "f1" | "f2" | "f3" | "f4" | "f5" | "f6";
export type Lamp = "fired" | "partial" | "watch" | "not" | "no_data";
export type Confidence = "high" | "medium" | "low";
export type FactorState = "ok" | "stale" | "low_coverage" | "failed";
export type RunStatus = "running" | "done" | "failed";
export type Stage = "early" | "mid" | "late";

export interface Evidence {
  evidence_id: string;
  run_id: string;
  factor: Factor;
  probe_id: string;
  window?: string | null;
  metric: string;
  value?: number | null;
  unit?: string | null;
  as_of?: string | null;
  quote?: string | null;
  source_url?: string | null;
  confidence: Confidence;
  provenance: Record<string, unknown>;
}

export interface RunEvent {
  id: number;
  run_id: string;
  ts: string;
  event_type: string;
  factor?: string | null;
  probe_id?: string | null;
  endpoint?: string | null;
  params_summary?: string | null;
  cost?: number | null;
  elapsed_ms?: number | null;
  cache_hit: boolean;
  detail: Record<string, unknown>;
}

export interface FactorResult {
  factor: Factor;
  score?: number | null;
  state: FactorState;
  sub_metrics: Record<string, unknown>;
  cost: number;
  as_of?: string | null;
}

export interface SignatureState {
  signature_id: string;
  lamp: Lamp;
  strong_count: number;
  weak_count: number;
  driving_evidence_ids: string[];
  name: string;
  factor: Factor;
  stage: Stage;
  threshold_text: string;
  k_weak: number;
  precedent_1999: string;
  precedent_citation_url?: string | null;
  current_reading: string;
  current_source_url?: string | null;
  confidence: Confidence;
  no_data_reason?: string | null;
}

export interface QuantCard {
  card_id: string;
  label: string;
  value?: number | null;
  unit: string;
  sparkline: number[];
  threshold?: number | null;
  threshold_label: string;
  source: string;
  as_of?: string | null;
}

export interface SeriesPoint {
  t: string;
  v: number;
}

export interface SignaturePin {
  signature_id: string;
  date: string;
  label: string;
  citation_url?: string | null;
}

export interface HeroSeries {
  era_1999: SeriesPoint[];
  era_now: SeriesPoint[];
  pins_1999: SignaturePin[];
  pins_now: SignaturePin[];
  peak_date_1999?: string | null;
}

export interface Thermometer {
  density?: number;
  baseline_1999?: number;
  score?: number;
  phrases?: { text: string; count: number; url?: string | null }[];
}

export interface StatePayload {
  run_id: string;
  status: RunStatus;
  updated_at: string;
  bti?: number | null;
  prev_bti?: number | null;
  stage_sentence: string;
  driven_by: string;
  fired_count: number;
  total_signatures: number;
  factors: FactorResult[];
  signatures: SignatureState[];
  quant_strip: QuantCard[];
  hero: HeroSeries;
  thermometer: Thermometer;
  danger_thresholds: Record<string, number>;
  evidence_count: number;
  citation_count: number;
  total_cost: number;
  config_version: string;
}

export interface RescoreResponse {
  run_id: string;
  status: RunStatus;
}
