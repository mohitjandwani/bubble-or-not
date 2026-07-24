import type { FactorResult, Factor, SignatureState } from "../types";
import { FACTOR_DESCRIPTIONS, FACTOR_NAMES, FACTOR_WEIGHTS, zoneColor } from "../constants";
import { cx, flashClass, fmtNum } from "../util";
import SignatureRow from "./SignatureRow";

interface Props {
  factor: Factor;
  result?: FactorResult;
  signatures: SignatureState[];
  openSignatureId: string | null;
  setOpenSignatureId: (id: string | null) => void;
  changed: Set<string>;
}

export default function FactorGroup({ factor, result, signatures, openSignatureId, setOpenSignatureId, changed }: Props) {
  const score = result?.score ?? null;
  const stale = result?.state && result.state !== "ok";

  return (
    <div id={`factor-group-${factor}`} className="factor-group panel">
      <div className="factor-header">
        <div className="name-desc">
          <div className="factor-name">{FACTOR_NAMES[factor]}</div>
          <div className="factor-desc">{FACTOR_DESCRIPTIONS[factor]}</div>
        </div>
        <div id={`factor-bar-${factor}`} className={cx("factor-bar-wrap", flashClass(changed, `factor-bar-${factor}`))}>
          <div
            className="factor-bar-fill"
            style={{ width: `${score ?? 0}%`, background: zoneColor(score), opacity: stale ? 0.8 : 1 }}
          />
        </div>
        <span className="factor-score tnum">{fmtNum(score, 0)}</span>
        <span className="weight-chip tnum">{Math.round(FACTOR_WEIGHTS[factor] * 100)}%</span>
        {stale && <span className="state-chip">{result?.state}</span>}
      </div>
      {signatures.map((s) => (
        <SignatureRow
          key={s.signature_id}
          signature={s}
          isOpen={openSignatureId === s.signature_id}
          onToggle={() => setOpenSignatureId(openSignatureId === s.signature_id ? null : s.signature_id)}
          changed={changed}
        />
      ))}
    </div>
  );
}
