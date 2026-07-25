/** Archival plates from the last consumer-tech mania. Presentational only. */

const PLATES = [
  {
    src: "/archive/win95-launch-crowd.webp",
    year: "1995",
    lead: "Midnight buyers hoist Windows 95 upgrades above a retail floor.",
    detail: "Software sold like stadium tickets. Queues formed before the doors opened.",
  },
  {
    src: "/archive/win95-retail-shelf.webp",
    year: "1995",
    lead: "Shelves stocked ahead of the launch: “Available from midnight.”",
    detail: "The supply build-out arrived first — demand was assumed, then priced.",
  },
];

export default function ArchiveBand() {
  return (
    <section className="block archive-band">
      <div className="section-title">
        Archive — the mania had a look before it had a chart
      </div>
      <div className="archive-grid">
        {PLATES.map((p) => (
          <figure className="archive-plate" key={p.src}>
            <div className="plate-frame">
              <img src={p.src} alt={p.lead} loading="lazy" decoding="async" />
              <span className="plate-year tnum">{p.year}</span>
              <span className="plate-sheen" aria-hidden="true" />
            </div>
            <figcaption className="plate-caption">
              <span className="plate-lead">{p.lead}</span>
              <span className="plate-detail">{p.detail}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
