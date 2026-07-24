const W = 110;
const H = 32;

export default function Sparkline({ values, threshold }: { values: number[]; threshold?: number | null }) {
  if (values.length < 2) return null;
  const all = threshold != null ? [...values, threshold] : values;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / span) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
      {threshold != null && (
        <line
          x1={0}
          x2={W}
          y1={H - ((threshold - min) / span) * H}
          y2={H - ((threshold - min) / span) * H}
          stroke="var(--dim)"
          strokeDasharray="3 3"
        />
      )}
      <polyline points={pts.join(" ")} fill="none" stroke="var(--cyan)" strokeWidth={1.5} />
    </svg>
  );
}
