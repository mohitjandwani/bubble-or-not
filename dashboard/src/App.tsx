import { useDashboardData } from "./hooks/useDashboardData";
import TopBar from "./components/TopBar";
import SectionA from "./components/SectionA";
import SectionB from "./components/SectionB";
import SectionC from "./components/SectionC";
import SectionD from "./components/SectionD";
import SectionE from "./components/SectionE";
import SectionF from "./components/SectionF";
import EventTicker from "./components/EventTicker";

export default function App() {
  const { state, offline, events, changed } = useDashboardData();

  if (!state) {
    return (
      <div>
        <TopBar state={null} offline={offline} changed={changed} />
        <div className="page">
          <p style={{ color: "var(--dim)", marginTop: 40 }}>Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <TopBar state={state} offline={offline} changed={changed} />
      <div className="page">
        <SectionA state={state} changed={changed} />
        <SectionB hero={state.hero} />
        <SectionC state={state} changed={changed} />
        <SectionD state={state} />
        <SectionE cards={state.quant_strip} />
        <SectionF state={state} />
      </div>
      <EventTicker events={events} visible={state.status === "running"} />
    </div>
  );
}
