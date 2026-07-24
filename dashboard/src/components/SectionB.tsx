import type { HeroSeries, SeriesPoint } from "../types";

const W = 1140;
const H = 380;

function toPoints(series: SeriesPoint[], minV: number, maxV: number): [number, number][] {
  const n = Math.max(series.length - 1, 1);
  return series.map((p, i) => {
    const x = (i / n) * W;
    const y = H - ((p.v - minV) / (maxV - minV || 1)) * H;
    return [x, y];
  });
}

function ptsToStr(pts: [number, number][]): string {
  return pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

export default function SectionB({ hero }: { hero: HeroSeries }) {
  const allVals = [...hero.era_1999, ...hero.era_now].map((p) => p.v);
  const minV = allVals.length ? Math.min(...allVals) : 0;
  const maxV = allVals.length ? Math.max(...allVals) : 100;

  const era1999Pts = toPoints(hero.era_1999, minV, maxV);
  const eraNowPts = toPoints(hero.era_now, minV, maxV);

  const peakIdx = hero.peak_date_1999
    ? hero.era_1999.findIndex((p) => p.t === hero.peak_date_1999)
    : -1;
  const splitIdx = peakIdx >= 0 ? peakIdx : era1999Pts.length;
  const prePeak = era1999Pts.slice(0, splitIdx + 1);
  const postPeak = era1999Pts.slice(splitIdx);

  return (
    <section className="block">
      <div className="section-title">Section B — Hero overlay chart</div>
      <div className="panel hero-chart-wrap">
        <div className="hero-toggle">
          <span>Price</span>
          <span>Rates</span>
        </div>
        <span className="era-caption era-1999" style={{ left: 20, bottom: 14 }}>
          1996–2001
        </span>
        <span className="era-caption era-now" style={{ left: 20, top: 40 }}>
          2023–now
        </span>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block" }}>
          {prePeak.length > 1 && (
            <polyline points={ptsToStr(prePeak)} stroke="var(--amber)" strokeWidth={2} fill="none" />
          )}
          {postPeak.length > 1 && (
            <polyline
              points={ptsToStr(postPeak)}
              stroke="var(--amber)"
              strokeWidth={2}
              fill="none"
              opacity={0.55}
            />
          )}
          {eraNowPts.length > 1 && (
            <polyline points={ptsToStr(eraNowPts)} stroke="var(--cyan)" strokeWidth={2.5} fill="none" />
          )}
        </svg>
      </div>
    </section>
  );
}
