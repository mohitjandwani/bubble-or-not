import { useEffect, useMemo, useRef, useState } from "react";
import type { HeroSeries, SeriesPoint, SignaturePin } from "../types";
import { cx, scrollToAndFlash } from "../util";
import HoverTip from "./HoverTip";

const W = 1140;
const H = 288;
const PAD_TOP = 16;
const PAD_BOTTOM = 16;
const TOTAL_H = H + PAD_TOP + PAD_BOTTOM;

type Pt = [number, number];
type Mode = "price" | "rates";

function dt(t: string): number {
  return new Date(t).getTime();
}

/** Fixture/API series should already be date-sorted, but guard against messy
 * upstream data so the polyline never zigzags backward. */
function sortByDate(series: SeriesPoint[]): SeriesPoint[] {
  return [...series].sort((a, b) => dt(a.t) - dt(b.t));
}

function seriesRange(series: SeriesPoint[]): [number, number] {
  if (series.length === 0) return [0, 1];
  return [dt(series[0].t), dt(series[series.length - 1].t)];
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/** Where a date falls within a series' own start-end span, as a 0-1 fraction.
 * This is the "phase position" the spec calls for — both eras render across the
 * same W pixels via their own date range, so equal phase = equal x pixel. */
function phaseOf(range: [number, number], dateStr: string): number {
  const [start, end] = range;
  if (end === start) return 0;
  return clamp01((dt(dateStr) - start) / (end - start));
}

function toPoints(series: SeriesPoint[], range: [number, number], minV: number, maxV: number): Pt[] {
  const span = maxV - minV || 1;
  return series.map((p) => {
    const x = phaseOf(range, p.t) * W;
    const y = H - ((p.v - minV) / span) * H;
    return [x, y] as Pt;
  });
}

function ptsToStr(pts: Pt[]): string {
  return pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

/** Linear-interpolate the pixel y of a polyline at pixel x — used to sit pins on
 * the line and to draw the "ghost" markers on the other era's line. */
function yAt(pts: Pt[], x: number): number {
  if (pts.length === 0) return H / 2;
  if (x <= pts[0][0]) return pts[0][1];
  if (x >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
  for (let i = 1; i < pts.length; i++) {
    if (pts[i][0] >= x) {
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      const f = x1 === x0 ? 0 : (x - x0) / (x1 - x0);
      return y0 + f * (y1 - y0);
    }
  }
  return pts[pts.length - 1][1];
}

function valueAtPhase(
  series: SeriesPoint[],
  range: [number, number],
  phase: number,
): { t: string; v: number } | null {
  if (series.length === 0) return null;
  const [start, end] = range;
  const targetTime = start + phase * (end - start);
  for (let i = 1; i < series.length; i++) {
    const t0 = dt(series[i - 1].t);
    const t1 = dt(series[i].t);
    if (t1 >= targetTime) {
      const f = t1 === t0 ? 0 : (targetTime - t0) / (t1 - t0);
      return { t: series[i - 1].t, v: series[i - 1].v + f * (series[i].v - series[i - 1].v) };
    }
  }
  return { t: series[series.length - 1].t, v: series[series.length - 1].v };
}

function fmtDate(t: string): string {
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return t;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
}

function fmtPrice(v: number): string {
  return v.toFixed(1);
}

function fmtRate(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}pp`;
}

interface RawPin {
  x: number;
  y: number;
  pin: SignaturePin;
  ghost: boolean;
}

interface StackedPin extends RawPin {
  level: number;
}

/** Stack pins vertically with a 4px offset when they fall within 8px of the
 * previous one horizontally, so a cluster of firings doesn't collide into a blob. */
function stackPins(raw: RawPin[]): StackedPin[] {
  const sorted = [...raw].sort((a, b) => a.x - b.x);
  let lastX: number | null = null;
  let level = 0;
  return sorted.map((r) => {
    if (lastX != null && Math.abs(r.x - lastX) <= 8) {
      level += 1;
    } else {
      level = 0;
    }
    lastX = r.x;
    return { ...r, level };
  });
}

function yearTicks(range: [number, number], startYear: number, endYear: number): { year: number; x: number }[] {
  const ticks: { year: number; x: number }[] = [];
  for (let y = startYear; y <= endYear; y++) {
    const jan1 = `${y}-01-01`;
    const t = dt(jan1);
    if (t < range[0] || t > range[1]) continue;
    ticks.push({ year: y, x: phaseOf(range, jan1) * W });
  }
  return ticks;
}

function trianglePath(px: number, py: number, size: number): string {
  // Downward-pointing pin (▼), tip sits at (px, py) on the line.
  return `M ${px - size},${py - size * 2} L ${px + size},${py - size * 2} L ${px},${py} Z`;
}

export default function SectionB({ hero }: { hero: HeroSeries }) {
  const [mode, setMode] = useState<Mode>("price");
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverPhase, setHoverPhase] = useState<number | null>(null);
  const [pinTip, setPinTip] = useState<{ x: number; y: number; content: React.ReactNode } | null>(null);

  // Rescore choreography: a signature that just fired gets a 200ms fall-in on
  // its new pin. Skipped on first mount so the initial page load stays calm.
  const prevPinsNowIdsRef = useRef<Set<string> | null>(null);
  const [fallingIn, setFallingIn] = useState<Set<string>>(new Set());
  useEffect(() => {
    const currentIds = new Set(hero.pins_now.map((p) => p.signature_id));
    const prev = prevPinsNowIdsRef.current;
    if (prev) {
      const newIds = [...currentIds].filter((id) => !prev.has(id));
      if (newIds.length > 0) {
        setFallingIn(new Set(newIds));
        const t = setTimeout(() => setFallingIn(new Set()), 260);
        prevPinsNowIdsRef.current = currentIds;
        return () => clearTimeout(t);
      }
    }
    prevPinsNowIdsRef.current = currentIds;
  }, [hero.pins_now]);

  const era1999 = useMemo(() => sortByDate(hero.era_1999), [hero.era_1999]);
  const eraNow = useMemo(() => sortByDate(hero.era_now), [hero.era_now]);
  const rates1999 = useMemo(() => sortByDate(hero.rates_1999), [hero.rates_1999]);
  const ratesNow = useMemo(() => sortByDate(hero.rates_now), [hero.rates_now]);

  const range1999 = useMemo(() => seriesRange(era1999), [era1999]);
  const rangeNow = useMemo(() => seriesRange(eraNow), [eraNow]);
  const rrange1999 = useMemo(() => seriesRange(rates1999), [rates1999]);
  const rrangeNow = useMemo(() => seriesRange(ratesNow), [ratesNow]);

  const priceVals = [...era1999, ...eraNow].map((p) => p.v);
  const priceMin = priceVals.length ? Math.min(...priceVals) : 0;
  const priceMax = priceVals.length ? Math.max(...priceVals) : 100;

  // Rates axis is symmetric around 0 pp, per spec.
  const rateVals = [...rates1999, ...ratesNow].map((p) => p.v);
  const rateAbsMax = rateVals.length ? Math.max(0.5, ...rateVals.map((v) => Math.abs(v))) : 0.5;
  const rateMin = -rateAbsMax;
  const rateMax = rateAbsMax;

  const pricePts1999 = useMemo(
    () => toPoints(era1999, range1999, priceMin, priceMax),
    [era1999, range1999, priceMin, priceMax],
  );
  const pricePtsNow = useMemo(
    () => toPoints(eraNow, rangeNow, priceMin, priceMax),
    [eraNow, rangeNow, priceMin, priceMax],
  );
  const ratePts1999 = useMemo(
    () => toPoints(rates1999, rrange1999, rateMin, rateMax),
    [rates1999, rrange1999, rateMin, rateMax],
  );
  const ratePtsNow = useMemo(
    () => toPoints(ratesNow, rrangeNow, rateMin, rateMax),
    [ratesNow, rrangeNow, rateMin, rateMax],
  );

  const peakX = hero.peak_date_1999 ? phaseOf(range1999, hero.peak_date_1999) * W : null;
  const prePeakPrice = peakX != null ? pricePts1999.filter((p) => p[0] <= peakX) : pricePts1999;
  const postPeakPrice = peakX != null ? pricePts1999.filter((p) => p[0] >= peakX) : [];

  const nowFiredIds = new Set(hero.pins_now.map((p) => p.signature_id));

  const pins1999Raw: RawPin[] = hero.pins_1999.map((pin) => {
    const x = phaseOf(range1999, pin.date) * W;
    return { x, y: yAt(pricePts1999, x), pin, ghost: false };
  });
  const pinsNowRealRaw: RawPin[] = hero.pins_now.map((pin) => {
    const x = phaseOf(rangeNow, pin.date) * W;
    return { x, y: yAt(pricePtsNow, x), pin, ghost: false };
  });
  // The visual punch: a 1999 pin with no counterpart yet renders as a faint
  // ghost slot on today's line, at the same phase % as the 1999 firing.
  const pinsNowGhostRaw: RawPin[] = hero.pins_1999
    .filter((pin) => !nowFiredIds.has(pin.signature_id))
    .map((pin) => {
      const x = phaseOf(range1999, pin.date) * W;
      return { x, y: yAt(pricePtsNow, x), pin, ghost: true };
    });

  const stacked1999 = stackPins(pins1999Raw);
  const stackedNow = stackPins([...pinsNowRealRaw, ...pinsNowGhostRaw]);

  function handleMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const fracX = clamp01((e.clientX - rect.left) / rect.width);
    setHoverPhase(fracX);
  }

  function handleLeave() {
    setHoverPhase(null);
  }

  const crosshairX = hoverPhase != null ? hoverPhase * W : null;
  const v1999AtHover =
    hoverPhase != null
      ? mode === "price"
        ? valueAtPhase(era1999, range1999, hoverPhase)
        : valueAtPhase(rates1999, rrange1999, hoverPhase)
      : null;
  const vNowAtHover =
    hoverPhase != null
      ? mode === "price"
        ? valueAtPhase(eraNow, rangeNow, hoverPhase)
        : valueAtPhase(ratesNow, rrangeNow, hoverPhase)
      : null;

  const yearsBottomPrice = yearTicks(range1999, 1996, 2001);
  const nowEndYearPrice = eraNow.length ? new Date(eraNow[eraNow.length - 1].t).getFullYear() : new Date().getFullYear();
  const yearsTopPrice = yearTicks(rangeNow, 2023, nowEndYearPrice);

  const rateStartYear1999 = rates1999.length ? new Date(rates1999[0].t).getFullYear() : 1999;
  const rateEndYear1999 = rates1999.length ? new Date(rates1999[rates1999.length - 1].t).getFullYear() : 2000;
  const yearsBottomRates = yearTicks(rrange1999, rateStartYear1999, rateEndYear1999);
  const rateStartYearNow = ratesNow.length ? new Date(ratesNow[0].t).getFullYear() : new Date().getFullYear();
  const rateEndYearNow = ratesNow.length ? new Date(ratesNow[ratesNow.length - 1].t).getFullYear() : new Date().getFullYear();
  const yearsTopRates = yearTicks(rrangeNow, rateStartYearNow, rateEndYearNow);

  const isEmpty = era1999.length === 0 && eraNow.length === 0;

  function pinTooltip(sp: StackedPin) {
    const anchorY = PAD_TOP + sp.y - 12 - sp.level * 4;
    const content = sp.ghost ? (
      <>
        <div className="tip-title tip-amber">{sp.pin.label}</div>
        <div>1999-era signature — hasn't fired yet today</div>
      </>
    ) : (
      <>
        <div className="tip-title">{sp.pin.label}</div>
        <div className="tnum">{fmtDate(sp.pin.date)}</div>
        {sp.pin.citation_url && (
          <a className="source-chip" href={sp.pin.citation_url} target="_blank" rel="noreferrer">
            source ↗
          </a>
        )}
      </>
    );
    setPinTip({ x: (sp.x / W) * 100, y: anchorY, content });
  }

  function renderPin(sp: StackedPin, color: string, isNowLine: boolean) {
    const y = sp.y - 4 - sp.level * 4;
    const opacity = sp.ghost ? 0.35 : 1;
    const isNew = isNowLine && !sp.ghost && fallingIn.has(sp.pin.signature_id);
    return (
      <path
        key={`${isNowLine ? "now" : "1999"}-${sp.pin.signature_id}`}
        className={cx(isNew && "pin-fall-in")}
        d={trianglePath(sp.x, y, 5)}
        fill={color}
        opacity={opacity}
        strokeDasharray={sp.ghost ? "2 2" : undefined}
        stroke={sp.ghost ? color : "none"}
        strokeWidth={sp.ghost ? 1 : 0}
        style={{ cursor: "pointer" }}
        onMouseEnter={() => pinTooltip(sp)}
        onMouseLeave={() => setPinTip(null)}
        onClick={() => scrollToAndFlash(sp.pin.signature_id)}
      />
    );
  }

  return (
    <section className="block">
      <div className="section-title">Section B — Hero overlay chart</div>
      <div className="panel hero-chart-wrap">
        <div className="hero-legend">
          <span className="legend-item">
            <span className="legend-swatch" style={{ background: "var(--amber)" }} />
            1999
          </span>
          <span className="legend-item">
            <span className="legend-swatch" style={{ background: "var(--cyan)" }} />
            Today
          </span>
        </div>

        <div className="hero-toggle" role="tablist" aria-label="Price or rates view">
          <button
            role="tab"
            aria-selected={mode === "price"}
            className={cx(mode === "price" && "active")}
            onClick={() => setMode("price")}
          >
            Price
          </button>
          <button
            role="tab"
            aria-selected={mode === "rates"}
            className={cx(mode === "rates" && "active")}
            onClick={() => setMode("rates")}
          >
            Rates
          </button>
        </div>

        {isEmpty ? (
          <div className="hero-skeleton" style={{ height: TOTAL_H }} />
        ) : (
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${TOTAL_H}`}
            width="100%"
            height={TOTAL_H}
            style={{ display: "block" }}
            onMouseMove={handleMove}
            onMouseLeave={handleLeave}
          >
            <rect x={0} y={0} width={W} height={TOTAL_H} fill="transparent" />
            <g transform={`translate(0, ${PAD_TOP})`}>
              {/* ---------- PRICE PANE ---------- */}
              <g
                style={{
                  opacity: mode === "price" ? 1 : 0,
                  transition: "opacity 250ms ease",
                  pointerEvents: mode === "price" ? "auto" : "none",
                }}
              >
                {prePeakPrice.length > 1 && (
                  <polyline points={ptsToStr(prePeakPrice)} stroke="var(--amber)" strokeWidth={2} fill="none" />
                )}
                {postPeakPrice.length > 1 && (
                  <polyline
                    points={ptsToStr(postPeakPrice)}
                    stroke="var(--amber)"
                    strokeWidth={2}
                    fill="none"
                    opacity={0.55}
                  />
                )}
                {pricePtsNow.length > 1 && (
                  <polyline points={ptsToStr(pricePtsNow)} stroke="var(--cyan)" strokeWidth={2.5} fill="none" />
                )}
                {pricePtsNow.length > 0 && (
                  <g className="live-dot-group">
                    <circle
                      cx={pricePtsNow[pricePtsNow.length - 1][0]}
                      cy={pricePtsNow[pricePtsNow.length - 1][1]}
                      r={3.5}
                      fill="var(--cyan)"
                      className="live-ping"
                    />
                    <circle
                      cx={pricePtsNow[pricePtsNow.length - 1][0]}
                      cy={pricePtsNow[pricePtsNow.length - 1][1]}
                      r={3.5}
                      fill="var(--cyan)"
                    />
                  </g>
                )}
                {stacked1999.map((sp) => renderPin(sp, "var(--amber)", false))}
                {stackedNow.map((sp) => renderPin(sp, sp.ghost ? "var(--dim)" : "var(--red)", true))}

                {yearsBottomPrice.map((yt) => (
                  <g key={`b-${yt.year}`}>
                    <line x1={yt.x} x2={yt.x} y1={H} y2={H + 4} stroke="var(--amber)" strokeWidth={1} />
                    <text x={yt.x} y={H + 15} fontSize={10} fill="var(--amber)" textAnchor="middle" className="tnum">
                      {yt.year}
                    </text>
                  </g>
                ))}
                {yearsTopPrice.map((yt) => (
                  <g key={`t-${yt.year}`}>
                    <line x1={yt.x} x2={yt.x} y1={-4} y2={0} stroke="var(--cyan)" strokeWidth={1} />
                    <text x={yt.x} y={-8} fontSize={10} fill="var(--cyan)" textAnchor="middle" className="tnum">
                      {yt.year}
                    </text>
                  </g>
                ))}
              </g>

              {/* ---------- RATES PANE ---------- */}
              <g
                style={{
                  opacity: mode === "rates" ? 1 : 0,
                  transition: "opacity 250ms ease",
                  pointerEvents: mode === "rates" ? "auto" : "none",
                }}
              >
                <line
                  x1={0}
                  x2={W}
                  y1={H - ((0 - rateMin) / (rateMax - rateMin || 1)) * H}
                  y2={H - ((0 - rateMin) / (rateMax - rateMin || 1)) * H}
                  stroke="var(--border)"
                  strokeWidth={1}
                />
                <text x={4} y={H - ((0 - rateMin) / (rateMax - rateMin || 1)) * H - 4} fontSize={9} fill="var(--dim)">
                  0.0pp
                </text>
                {ratePts1999.length > 1 && (
                  <polyline points={ptsToStr(ratePts1999)} stroke="var(--amber)" strokeWidth={2} fill="none" />
                )}
                {ratePtsNow.length > 1 && (
                  <polyline points={ptsToStr(ratePtsNow)} stroke="var(--cyan)" strokeWidth={2.5} fill="none" />
                )}
                {yearsBottomRates.map((yt) => (
                  <g key={`rb-${yt.year}`}>
                    <line x1={yt.x} x2={yt.x} y1={H} y2={H + 4} stroke="var(--amber)" strokeWidth={1} />
                    <text x={yt.x} y={H + 15} fontSize={10} fill="var(--amber)" textAnchor="middle" className="tnum">
                      {yt.year}
                    </text>
                  </g>
                ))}
                {yearsTopRates.map((yt) => (
                  <g key={`rt-${yt.year}`}>
                    <line x1={yt.x} x2={yt.x} y1={-4} y2={0} stroke="var(--cyan)" strokeWidth={1} />
                    <text x={yt.x} y={-8} fontSize={10} fill="var(--cyan)" textAnchor="middle" className="tnum">
                      {yt.year}
                    </text>
                  </g>
                ))}
              </g>

              {crosshairX != null && (
                <line x1={crosshairX} x2={crosshairX} y1={0} y2={H} stroke="var(--dim)" strokeWidth={1} strokeDasharray="3 3" />
              )}
            </g>
          </svg>
        )}

        {hoverPhase != null && v1999AtHover && vNowAtHover && (
          <HoverTip leftPct={hoverPhase * 100} topPx={PAD_TOP + 18}>
            <div className="tip-title">phase {Math.round(hoverPhase * 100)}%</div>
            <div className="tip-amber tnum">
              1999 · {fmtDate(v1999AtHover.t)} · {mode === "price" ? fmtPrice(v1999AtHover.v) : fmtRate(v1999AtHover.v)}
            </div>
            <div className="tip-cyan tnum">
              today · {fmtDate(vNowAtHover.t)} · {mode === "price" ? fmtPrice(vNowAtHover.v) : fmtRate(vNowAtHover.v)}
            </div>
          </HoverTip>
        )}

        {pinTip && (
          <HoverTip leftPct={pinTip.x} topPx={pinTip.y}>
            {pinTip.content}
          </HoverTip>
        )}
      </div>
    </section>
  );
}
