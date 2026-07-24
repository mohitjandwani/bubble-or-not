import type { StatePayload } from "../types";
import RadarChart from "./RadarChart";
import Thermometer from "./Thermometer";

export default function SectionD({ state }: { state: StatePayload }) {
  const resultsByFactor = Object.fromEntries(state.factors.map((f) => [f.factor, f]));
  const phrases = state.thermometer.phrases ?? [];

  return (
    <section className="block d-grid">
      <div className="panel d-cell">
        <div className="section-title">Section D1 — Radar (today vs danger thresholds)</div>
        <RadarChart scores={resultsByFactor} thresholds={state.danger_thresholds} />
      </div>
      <div className="panel d-cell">
        <div className="section-title">Section D2 — Narrative thermometer</div>
        <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
          <Thermometer data={state.thermometer} />
          <div style={{ flex: 1 }}>
            {phrases.map((p) => (
              <div className="phrase-row" key={p.text}>
                <span>"{p.text}"</span>
                <span className="tnum">{p.count}×</span>
              </div>
            ))}
          </div>
        </div>
        <div className="thermo-badge">Coincident indicator — display only, excluded from BTI.</div>
      </div>
    </section>
  );
}
