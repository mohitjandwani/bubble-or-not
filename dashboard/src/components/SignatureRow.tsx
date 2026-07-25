import type { F3Exhibit, SignatureState } from "../types";
import { confidenceColor, lampColor } from "../constants";
import { cx, flashClass } from "../util";
import EvidenceDrawer from "./EvidenceDrawer";

interface Props {
  signature: SignatureState;
  isOpen: boolean;
  onToggle: () => void;
  changed: Set<string>;
  f3?: F3Exhibit;
}

export default function SignatureRow({ signature: s, isOpen, onToggle, changed, f3 }: Props) {
  const isSpecialLamp = s.lamp === "watch" || s.lamp === "no_data";
  const lampChanged = changed.has(s.signature_id);
  return (
    <div id={s.signature_id}>
      <div className={cx("sig-row", flashClass(changed, s.signature_id))} onClick={onToggle}>
        <span
          className={cx("lamp", s.lamp, lampChanged && "lamp-pulse")}
          style={isSpecialLamp ? undefined : { background: lampColor(s.lamp) }}
          title={s.lamp === "no_data" ? s.no_data_reason ?? "no data" : s.lamp}
        />
        <span className="sig-name">{s.name}</span>
        <span className="sig-counters tnum">
          S:{s.strong_count} W:{s.weak_count}
        </span>
        <span className="sig-precedent" title={s.precedent_1999}>
          {s.precedent_1999}
        </span>
        <span className="sig-current" title={s.current_reading}>
          {s.current_reading}
        </span>
        <span
          className="confidence-dot"
          style={{ background: confidenceColor(s.confidence) }}
          title={`confidence: ${s.confidence}`}
        />
        <span className="threshold-hint">{s.threshold_text}</span>
      </div>
      {isOpen && <EvidenceDrawer signature={s} f3={s.factor === "f3" ? f3 : undefined} />}
    </div>
  );
}
