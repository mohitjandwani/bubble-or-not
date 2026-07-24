import type { StatePayload } from "../types";
import { fmtTime } from "../util";

export default function SectionF({ state }: { state: StatePayload }) {
  return (
    <footer className="block">
      <div>
        <a href="#">Methodology</a>
        <a href="#">Built on You.com Research APIs</a>
      </div>
      <div className="tnum">
        {state.evidence_count} evidence objects · {state.citation_count} citations · last full run{" "}
        {fmtTime(state.updated_at)}
      </div>
      <div>Evidence aggregation, not investment advice.</div>
    </footer>
  );
}
