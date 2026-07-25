/** Full-bleed archival masthead. Purely presentational — no data, no state. */
export default function Masthead() {
  return (
    <header className="masthead">
      <div className="masthead-media" aria-hidden="true">
        <img src="/archive/nasdaq-times-square.jpg" alt="" loading="eager" decoding="async" />
        <div className="masthead-duotone" />
        <div className="masthead-grain" />
        <div className="masthead-scrim" />
      </div>

      <div className="masthead-inner">
        <div className="masthead-eyebrow">
          <span className="eyebrow-dot" />
          Multi-agent evidence engine · live
        </div>
        <h1 className="masthead-title">
          <span className="mh-word" style={{ animationDelay: "80ms" }}>
            Bubble
          </span>{" "}
          <span className="mh-word mh-word-dim" style={{ animationDelay: "200ms" }}>
            or
          </span>{" "}
          <span className="mh-word" style={{ animationDelay: "320ms" }}>
            Not
          </span>
        </h1>
        <div className="masthead-rule" />
        <p className="masthead-deck">
          Is AI the new dot-com? Historical bubble signatures, prosecuted live against today's market.
          <br />
          <span className="deck-em">LLMs gather the evidence — the scores are computed, never generated.</span>
        </p>
      </div>

      <div className="masthead-credit">Nasdaq MarketSite · Times Square</div>
      <div className="masthead-tape" aria-hidden="true" />
    </header>
  );
}
