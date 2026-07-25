import { useDashboardData } from "./hooks/useDashboardData";
import TopBar from "./components/TopBar";
import Masthead from "./components/Masthead";
import ArchiveBand from "./components/ArchiveBand";
import Reveal from "./components/Reveal";
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
        <Masthead />
        <div className="page">
          <p className="loading-line" style={{ marginTop: 40 }}>
            Loading<span className="loading-dots" />
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <TopBar state={state} offline={offline} changed={changed} />
      <Masthead />
      <div className="page">
        <Reveal>
          <SectionA state={state} changed={changed} />
        </Reveal>
        <Reveal delay={60}>
          <SectionB hero={state.hero} />
        </Reveal>
        <Reveal>
          <SectionC state={state} changed={changed} />
        </Reveal>
        <Reveal>
          <ArchiveBand />
        </Reveal>
        <Reveal>
          <SectionD state={state} />
        </Reveal>
        <Reveal>
          <SectionE cards={state.quant_strip} />
        </Reveal>
        <Reveal>
          <SectionF state={state} />
        </Reveal>
      </div>
      <EventTicker events={events} visible={state.status === "running"} />
    </div>
  );
}
