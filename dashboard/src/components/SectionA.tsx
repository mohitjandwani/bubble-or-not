import type { StatePayload } from "../types";
import { lampColor } from "../constants";
import { cx, flashClass, scrollToAndFlash } from "../util";
import { useCrossfade, useTweenedNumber } from "../hooks/useAnimatedValue";
import Gauge from "./Gauge";

interface Props {
  state: StatePayload;
  changed: Set<string>;
}

function lampLabel(lamp: string): string {
  switch (lamp) {
    case "fired":
      return "fired";
    case "partial":
      return "partial";
    case "watch":
      return "watching";
    case "no_data":
      return "no data";
    default:
      return "not fired";
  }
}

export default function SectionA({ state, changed }: Props) {
  const delta = state.bti != null && state.prev_bti != null ? state.bti - state.prev_bti : null;
  const rising = delta != null && delta > 0;
  const btiDisplay = useTweenedNumber(state.bti, 1200);

  const sentenceCf = useCrossfade(state.stage_sentence, 250);
  const drivenByCf = useCrossfade(state.driven_by, 250);

  // Dots that changed lamp this run, in board order — drives the 300ms stagger.
  const changedDotOrder = state.signatures
    .filter((s) => changed.has(`dot-${s.signature_id}`))
    .map((s) => s.signature_id);

  return (
    <section className="block verdict-grid">
      <div className="panel verdict-cell">
        <Gauge value={state.bti} />
        <div>
          <span id="bti-number" className={cx("bti-number tnum", flashClass(changed, "bti-number"))}>
            {state.bti == null ? "—" : btiDisplay.toFixed(1)}
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
          {state.signatures.map((s) => {
            const dotId = `dot-${s.signature_id}`;
            const staggerIdx = changedDotOrder.indexOf(s.signature_id);
            return (
              <span key={s.signature_id} className="tip-wrap" data-tip={`${s.name} — ${lampLabel(s.lamp)}`}>
                <button
                  id={dotId}
                  className={cx("sig-dot", s.lamp, flashClass(changed, dotId))}
                  style={{
                    ...(s.lamp === "watch" || s.lamp === "no_data" ? undefined : { background: lampColor(s.lamp) }),
                    transitionDelay: staggerIdx >= 0 ? `${staggerIdx * 300}ms` : "0ms",
                  }}
                  aria-label={`${s.name} — ${lampLabel(s.lamp)}, jump to evidence row`}
                  onClick={() => scrollToAndFlash(s.signature_id)}
                />
              </span>
            );
          })}
        </div>
      </div>

      <div className="panel verdict-cell">
        <p className={cx("stage-sentence crossfade", sentenceCf.visible ? "cf-in" : "cf-out")}>
          {sentenceCf.display}
        </p>
        {drivenByCf.display && (
          <div className={cx("driven-by crossfade", drivenByCf.visible ? "cf-in" : "cf-out")}>
            {drivenByCf.display}
          </div>
        )}
      </div>
    </section>
  );
}
