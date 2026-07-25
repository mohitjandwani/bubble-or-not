import { useMemo } from "react";
import { useEngineData, useEngineTrace } from "../hooks/useEngineData";
import { FACTOR_NAMES } from "../constants";
import type { EngineProbe, Factor } from "../types";
import ProbeCard from "./ProbeCard";
import TraceFeed from "./TraceFeed";

// Engine tab covers all six factors (F6 narrative-temp included), unlike the
// Verdict signature board which only shows F1-F5's scored signatures.
const ENGINE_FACTOR_ORDER: Factor[] = ["f1", "f2", "f3", "f4", "f5", "f6"];

export default function EngineTab() {
  const { engine, error } = useEngineData();
  const events = useEngineTrace();

  const grouped = useMemo(() => {
    const map: Partial<Record<Factor, EngineProbe[]>> = {};
    if (!engine) return map;
    for (const p of engine.probes) {
      (map[p.factor] ??= []).push(p);
    }
    return map;
  }, [engine]);

  const totalCost = useMemo(
    () => (engine ? engine.probes.reduce((sum, p) => sum + p.cost_est_usd, 0) : 0),
    [engine],
  );

  return (
    <div className="page">
      <section className="block">
        <div className="section-title">Engine — API usage exhibit</div>
        <div className="panel engine-header">
          {!engine && error ? (
            <div className="engine-offline">Engine data unavailable — backend offline.</div>
          ) : !engine ? (
            <div className="hero-skeleton" style={{ height: 74 }} />
          ) : (
            <>
              <div className="engine-stats-row">
                <div className="engine-stat">
                  <div className="engine-stat-label">You.com credits</div>
                  <div className="engine-stat-value tnum">
                    {engine.balance_usd != null ? `$${engine.balance_usd.toFixed(2)}` : "—"}
                  </div>
                </div>
                <div className="engine-stat">
                  <div className="engine-stat-label">Est. cost / full run</div>
                  <div className="engine-stat-value tnum">${totalCost.toFixed(2)}</div>
                </div>
                <div className="engine-stat">
                  <div className="engine-stat-label">Probes</div>
                  <div className="engine-stat-value tnum">{engine.probes.length}</div>
                </div>
              </div>
              <div className="engine-pricing-note tnum">{engine.pricing_note}</div>
              <div className="engine-tagline">
                LLMs gather evidence; scores are computed — every call below is auditable.
              </div>
            </>
          )}
        </div>
      </section>

      <section className="block engine-grid">
        <div className="engine-map">
          <div className="section-title">API usage map</div>
          {!engine && !error && <div className="hero-skeleton" style={{ height: 240 }} />}
          {ENGINE_FACTOR_ORDER.map((f) => {
            const probes = grouped[f];
            if (!probes || probes.length === 0) return null;
            return (
              <div key={f} className="panel engine-factor-group">
                <div className="engine-factor-header">{FACTOR_NAMES[f]}</div>
                {probes.map((p) => (
                  <ProbeCard key={p.probe_id} probe={p} stat={engine?.probe_stats[p.probe_id]} />
                ))}
              </div>
            );
          })}
        </div>
        <div className="engine-trace-col">
          <div className="section-title">Live trace</div>
          <TraceFeed events={events} />
        </div>
      </section>
    </div>
  );
}
