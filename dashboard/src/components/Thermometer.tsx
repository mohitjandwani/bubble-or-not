import type { Thermometer as ThermometerData } from "../types";

const H = 220;
const W = 40;

export default function Thermometer({ data }: { data: ThermometerData }) {
  // Fill and baseline tick MUST share one scale or the picture lies
  // (density 0.31 must render BELOW baseline 0.47). Both are raw density
  // fractions; scale so the larger of the two sits at ~70% height.
  const density = data.density ?? 0;
  const baseline = data.baseline_1999 ?? 0;
  const scaleMax = Math.max(density, baseline) / 0.7 || 1;
  const fillHeight = Math.min(1, density / scaleMax) * H;
  const baselineY = H - Math.min(1, baseline / scaleMax) * H;

  return (
    <div>
      <svg viewBox={`0 0 120 ${H + 20}`} width={120} height={H + 20}>
        <rect x={40} y={10} width={W} height={H} rx={20} fill="none" stroke="var(--border)" strokeWidth={2} />
        <rect
          x={40}
          y={10 + (H - fillHeight)}
          width={W}
          height={fillHeight}
          rx={20}
          fill="var(--amber)"
        />
        <line x1={30} y1={10 + baselineY} x2={90} y2={10 + baselineY} stroke="var(--dim)" strokeDasharray="3 3" />
        <text x={95} y={10 + baselineY + 4} fontSize={9} fill="var(--dim)">
          1999 peak baseline
        </text>
      </svg>
    </div>
  );
}
