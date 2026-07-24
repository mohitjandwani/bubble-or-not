import type { RunEvent } from "../types";

export default function EventTicker({ events, visible }: { events: RunEvent[]; visible: boolean }) {
  if (!visible || events.length === 0) return null;
  return (
    <div className="event-ticker">
      {events.slice(-5).map((e) => (
        <div className="ev-line" key={e.id}>
          {e.event_type} {e.factor ?? ""} {e.probe_id ?? ""} {e.cost != null ? `$${e.cost.toFixed(2)}` : ""}
        </div>
      ))}
    </div>
  );
}
