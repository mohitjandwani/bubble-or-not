import { useEffect, useState } from "react";
import { useDashboardData } from "./hooks/useDashboardData";
import TopBar, { type Tab } from "./components/TopBar";
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
import EngineTab from "./components/EngineTab";

function tabFromHash(): Tab {
  return window.location.hash.replace("#", "") === "engine" ? "engine" : "verdict";
}

export default function App() {
  const { state, offline, events, changed } = useDashboardData();
  const [tab, setTab] = useState<Tab>(() => tabFromHash());

  // Deep-linkable: #engine opens Screen 2 directly, and the back/forward
  // buttons or a manually-edited hash keep the tab in sync with the URL.
  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function selectTab(next: Tab) {
    window.location.hash = next === "engine" ? "engine" : "";
    setTab(next);
  }

  if (tab === "engine") {
    return (
      <div>
        <TopBar state={state} offline={offline} changed={changed} tab={tab} onTabChange={selectTab} />
        <EngineTab />
      </div>
    );
  }

  if (!state) {
    return (
      <div>
        <TopBar state={null} offline={offline} changed={changed} tab={tab} onTabChange={selectTab} />
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
      <TopBar state={state} offline={offline} changed={changed} tab={tab} onTabChange={selectTab} />
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
