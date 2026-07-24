// Rough half-donut gauge: three colored zone arcs + a needle. Crude by design (Pass 1).
const CX = 100;
const CY = 100;
const R = 82;

function polar(angleDeg: number, r = R) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY - r * Math.sin(rad) };
}

function arc(fromAngle: number, toAngle: number, color: string) {
  const a = polar(fromAngle);
  const b = polar(toAngle);
  return (
    <path
      key={color}
      d={`M ${a.x} ${a.y} A ${R} ${R} 0 0 1 ${b.x} ${b.y}`}
      stroke={color}
      strokeWidth={14}
      fill="none"
      strokeLinecap="butt"
    />
  );
}

export default function Gauge({ value }: { value: number | null | undefined }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const needleAngle = 180 - (v / 100) * 180;
  const tip = polar(needleAngle, R - 16);
  return (
    <svg viewBox="0 0 200 110" width="100%" height="90">
      {arc(180, 108, "var(--green)")}
      {arc(108, 54, "var(--amber)")}
      {arc(54, 0, "var(--red)")}
      {value != null && (
        <line x1={CX} y1={CY} x2={tip.x} y2={tip.y} stroke="var(--text)" strokeWidth={3} strokeLinecap="round" />
      )}
      <circle cx={CX} cy={CY} r={4} fill="var(--text)" />
    </svg>
  );
}
