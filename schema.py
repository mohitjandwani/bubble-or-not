"""The contract. Every layer — pipeline, Postgres rows, API payloads, SPA — speaks these shapes.

Field names deliberately match the Postgres DDL in hackathon_handoff/agents-README.md §6,
so Pass 2 (swap in-memory store → Postgres) is a storage change, not a schema change.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Factor = Literal["f1", "f2", "f3", "f4", "f5", "f6"]
Lamp = Literal["fired", "partial", "watch", "not", "no_data"]
Confidence = Literal["high", "medium", "low"]
FactorState = Literal["ok", "stale", "low_coverage", "failed"]
RunStatus = Literal["running", "done", "failed"]
Stage = Literal["early", "mid", "late"]

FACTOR_WEIGHTS: dict[str, float] = {"f1": 0.25, "f2": 0.20, "f3": 0.20, "f4": 0.15, "f5": 0.20}
# f6 displayed, weight 0 — excluded from BTI by design.


class Evidence(BaseModel):
    """One typed fact gathered by a probe. LLMs fill these; code scores them."""

    evidence_id: str
    run_id: str
    factor: Factor
    probe_id: str
    window: Optional[str] = None
    metric: str
    value: Optional[float] = None
    unit: Optional[str] = None
    as_of: Optional[date] = None
    quote: Optional[str] = None
    source_url: Optional[str] = None
    confidence: Confidence = "medium"
    provenance: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    """Trace row. `id` is the monotonic cursor for GET /events?since=."""

    id: int
    run_id: str
    ts: datetime
    event_type: str  # run.started | agent.started | agent.tool_call | agent.evidence
    #                | agent.completed | agent.failed | run.completed
    factor: Optional[str] = None
    probe_id: Optional[str] = None
    endpoint: Optional[str] = None
    params_summary: Optional[str] = None
    cost: Optional[float] = None
    elapsed_ms: Optional[int] = None
    cache_hit: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class FactorResult(BaseModel):
    factor: Factor
    score: Optional[float] = None  # 0-100; None only when never computed
    state: FactorState = "ok"
    sub_metrics: dict[str, Any] = Field(default_factory=dict)
    cost: float = 0.0
    as_of: Optional[datetime] = None  # last good compute (drives the "stale · <ts>" chip)


class SignatureState(BaseModel):
    """Lamp + counters for one board row. Display metadata is merged in from config
    server-side so the SPA stays dumb."""

    signature_id: str
    lamp: Lamp
    strong_count: int = 0
    weak_count: int = 0
    driving_evidence_ids: list[str] = Field(default_factory=list)
    # merged from /config/signatures.yaml:
    name: str
    factor: Factor
    stage: Stage
    threshold_text: str  # the "fires when …" hover rule
    k_weak: int  # weak-cluster threshold for PARTIAL
    precedent_1999: str
    precedent_citation_url: Optional[str] = None
    current_reading: str  # one bright line, e.g. "Median NTM revision +1.8% — still positive"
    current_source_url: Optional[str] = None
    confidence: Confidence = "medium"
    no_data_reason: Optional[str] = None  # honest tooltip for hatched rows


class QuantCard(BaseModel):
    """Section E card — 'no LLM in this row'."""

    card_id: str
    label: str
    value: Optional[float] = None
    unit: str = ""
    sparkline: list[float] = Field(default_factory=list)  # trailing 12 months, downsampled
    threshold: Optional[float] = None
    threshold_label: str = ""
    source: str = ""  # domain chip, e.g. "fmp"
    as_of: Optional[str] = None


class SeriesPoint(BaseModel):
    t: str  # ISO date
    v: float


class SignaturePin(BaseModel):
    signature_id: str
    date: str  # ISO date on that era's axis
    label: str
    citation_url: Optional[str] = None


class HeroSeries(BaseModel):
    """Section B data. Both eras indexed to 100 at era start, weekly points."""

    era_1999: list[SeriesPoint] = Field(default_factory=list)
    era_now: list[SeriesPoint] = Field(default_factory=list)
    pins_1999: list[SignaturePin] = Field(default_factory=list)
    pins_now: list[SignaturePin] = Field(default_factory=list)
    peak_date_1999: Optional[str] = None  # crash segment (post-peak) renders dimmed


class StatePayload(BaseModel):
    """GET /state — the one payload the public SPA lives on."""

    run_id: str
    status: RunStatus
    updated_at: datetime
    bti: Optional[float] = None
    prev_bti: Optional[float] = None
    stage_sentence: str = ""
    driven_by: str = ""  # "Driven by: Liquidity +2.1"
    fired_count: int = 0
    total_signatures: int = 12
    factors: list[FactorResult] = Field(default_factory=list)
    signatures: list[SignatureState] = Field(default_factory=list)  # board order
    quant_strip: list[QuantCard] = Field(default_factory=list)
    hero: HeroSeries = Field(default_factory=HeroSeries)
    thermometer: dict[str, Any] = Field(default_factory=dict)  # f6 density, baseline, phrases[]
    danger_thresholds: dict[str, float] = Field(default_factory=dict)  # radar dashed outline
    evidence_count: int = 0
    citation_count: int = 0
    total_cost: float = 0.0
    config_version: str = "dev"


class RescoreResponse(BaseModel):
    run_id: str
    status: RunStatus


def compute_bti(factor_scores: dict[str, Optional[float]]) -> Optional[float]:
    """BTI = Σ weight·score over f1..f5. A factor with no score ever (None) is
    excluded and weights renormalize — 'stale' factors still carry their last-good score."""
    parts = [(FACTOR_WEIGHTS[f], s) for f, s in factor_scores.items() if f in FACTOR_WEIGHTS and s is not None]
    if not parts:
        return None
    total_w = sum(w for w, _ in parts)
    return round(sum(w * s for w, s in parts) / total_w, 1)


def stage_sentence(signatures: list[SignatureState]) -> tuple[str, int]:
    """Deterministic template over fired stage-buckets. Never LLM-generated at render time."""
    fired = [s for s in signatures if s.lamp == "fired"]
    buckets = {s.stage for s in fired}
    n = len(fired)
    if not buckets:
        sent = "No 1999-style triggers have fired. Conditions do not resemble a late-stage bubble."
    elif buckets == {"early"}:
        sent = "Conditions resemble early-stage 1999. Mid- and late-stage triggers have not fired."
    elif "late" in buckets and {"early", "mid"} & buckets:
        sent = "Conditions resemble late-stage 1999. Early-, mid- and late-stage triggers are all firing."
    elif "late" in buckets:
        sent = "Late-stage triggers are firing without the usual early-stage buildup — an atypical pattern."
    elif "mid" in buckets:
        sent = ("Conditions resemble mid-stage 1999. Late-stage triggers — bellwether cracks, "
                "insider selling wave — have not fired.")
    else:
        sent = "Scattered triggers are firing across stages."
    return sent, n
