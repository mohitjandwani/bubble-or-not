import type { StatePayload } from "../types";
import { lampColor } from "../constants";
import { cx, flashClass, fmtNum } from "../util";
import Gauge from "./Gauge";

interface Props {
  state: StatePayload;
  changed: Set<string>;
}

function scrollToSignature(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

export default function SectionA({ state, changed }: Props) {
  const delta = state.bti != null && state.prev_bti != null ? state.bti - state.prev_bti : null;
  const rising = delta != null && delta > 0;

  return (
    <section className="block verdict-grid">
      <div className="panel verdict-cell">
        <Gauge value={state.bti} />
        <div>
          <span id="bti-number" className={cx("bti-number tnum", flashClass(changed, "bti-number"))}>
            {fmtNum(state.bti)}
          </span>
          {delta != null && (
            <span className={cx("bti-delta tnum", rising ? "up" : "down")}>
              {rising ? "+" : ""}
              {delta.toFixed(1)} {rising ? "▲" : "▼"}
            </span>
          )}
        </div>
      </div>

      <div className="panel verdict-cell">
        <div className="sig-counter-headline tnum">
          {state.fired_count} / {state.total_signatures} signatures fired
        </div>
        <div className="sig-dots">
          {state.signatures.map((s) => (
            <button
              key={s.signature_id}
              id={`dot-${s.signature_id}`}
              className={cx("sig-dot", s.lamp, flashClass(changed, `dot-${s.signature_id}`))}
              style={s.lamp === "watch" || s.lamp === "no_data" ? undefined : { background: lampColor(s.lamp) }}
              title={`${s.name} — ${s.lamp}`}
              onClick={() => scrollToSignature(s.signature_id)}
            />
          ))}
        </div>
      </div>

      <div className="panel verdict-cell">
        <p className="stage-sentence">{state.stage_sentence}</p>
        {state.driven_by && <div className="driven-by">{state.driven_by}</div>}
      </div>
    </section>
  );
}
