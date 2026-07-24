import { useState } from "react";
import type { StatePayload } from "../types";
import { FACTOR_ORDER } from "../constants";
import FactorGroup from "./FactorGroup";

export default function SectionC({ state, changed }: { state: StatePayload; changed: Set<string> }) {
  const [openSignatureId, setOpenSignatureId] = useState<string | null>(null);
  const resultsByFactor = new Map(state.factors.map((f) => [f.factor, f]));

  return (
    <section className="block">
      <div className="section-title">Section C — Signature board</div>
      {FACTOR_ORDER.map((factor) => (
        <FactorGroup
          key={factor}
          factor={factor}
          result={resultsByFactor.get(factor)}
          signatures={state.signatures.filter((s) => s.factor === factor)}
          openSignatureId={openSignatureId}
          setOpenSignatureId={setOpenSignatureId}
          changed={changed}
        />
      ))}
    </section>
  );
}
