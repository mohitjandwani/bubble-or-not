import type { QuantCard } from "../types";
import { fmtNum } from "../util";
import Sparkline from "./Sparkline";

export default function SectionE({ cards }: { cards: QuantCard[] }) {
  return (
    <section className="block">
      <div className="section-title">Section E — Quant strip</div>
      <div className="quant-caption">Computed directly from market data — no model in the loop.</div>
      <div className="quant-grid">
        {cards.map((c) => (
          <div key={c.card_id} className="panel quant-card">
            <div className="quant-label">{c.label}</div>
            <div>
              <span className="quant-value tnum">{fmtNum(c.value)}</span>
              <span className="quant-unit">{c.unit}</span>
            </div>
            <Sparkline values={c.sparkline} threshold={c.threshold} />
            <div className="quant-source-row">
              <span>{c.source}</span>
              <span className="tnum">{c.as_of ?? "—"}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
