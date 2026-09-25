import { useState } from "react";
import {
  IconPerson,
  IconOrg,
  IconLocation,
  IconPipeline,
  IconExternal,
  IconChevron,
  IconGlobe,
  IconDoc,
  IconTrash,
  IconPlay,
  IconInfo,
} from "./icons.jsx";
import { linkText, getRelations } from "./apiClient.js";

const CONFIDENCE_HINT =
  "This is the disambiguation confidence: cosine similarity between the mention's context and the " +
  "top-ranked candidate's description. It is not an NER detection score — the NER stage doesn't " +
  "expose its own per-mention confidence.";

const SOURCE_LABELS = {
  local_cache: "Local KB cache",
  live_search: "Live Wikidata search",
};

function InfoHint({ text }) {
  return (
    <span className="info-hint" title={text}>
      <IconInfo />
    </span>
  );
}

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "hi", name: "Hindi" },
  { code: "es", name: "Spanish" },
  { code: "de", name: "German" },
];

const LABEL_META = {
  PER: { name: "Person", Icon: IconPerson },
  ORG: { name: "Organization", Icon: IconOrg },
  LOC: { name: "Location", Icon: IconLocation },
};

const EXAMPLES = {
  en: [
    "Amazon announced record cloud revenue this quarter.",
    "The Amazon river flows through Brazil into the Atlantic.",
    "Barack Obama met Angela Merkel in Berlin.",
  ],
  hi: ["भारत के प्रधानमंत्री नरेंद्र मोदी ने संयुक्त राष्ट्र में भाषण दिया।"],
  es: ["El presidente de España visitó Alemania la semana pasada."],
  de: ["Der Bundeskanzler Olaf Scholz hat bei den Vereinten Nationen eine Rede gehalten."],
};

const PIPELINE_STEPS = ["NER", "Candidate generation", "Disambiguation", "Wikidata linking"];

function labelMeta(label) {
  return LABEL_META[label] || { name: label, Icon: IconLocation };
}

function highlightedText(text, mentions, selectedIdx, onSelect) {
  if (!mentions.length) return [text];
  const sorted = mentions.map((m, i) => ({ ...m, _i: i })).sort((a, b) => a.start_char - b.start_char);
  const parts = [];
  let cursor = 0;

  sorted.forEach((m) => {
    if (m.start_char > cursor) parts.push(text.slice(cursor, m.start_char));
    parts.push(
      <span
        key={m._i}
        className={`mention type-${m.label} ${m._i === selectedIdx ? "mention-selected" : ""}`}
        onClick={() => onSelect(m._i)}
      >
        {text.slice(m.start_char, m.end_char)}
      </span>
    );
    cursor = m.end_char;
  });

  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

function PipelineStepper({ phase }) {
  // phase: -1 idle, 0-3 running (cycling), 4 done
  return (
    <div className="stepper">
      {PIPELINE_STEPS.map((label, i) => {
        const state = phase === 4 || phase > i ? "done" : phase === i ? "active" : "idle";
        return (
          <div className="step" key={label}>
            <div className={`step-circle ${state}`}>{i + 1}</div>
            <div className="step-label">{label}</div>
            {i < PIPELINE_STEPS.length - 1 && <div className={`step-line ${phase > i || phase === 4 ? "done" : ""}`} />}
          </div>
        );
      })}
    </div>
  );
}

function DisambiguationGraph({ mention, compact = false, maxCandidates = 6 }) {
  const candidates = mention.candidates.slice(0, maxCandidates);
  const overflow = mention.candidates.length - candidates.length;
  const n = candidates.length;

  const positions = candidates.map((c, i) => {
    const angle = (-90 + (360 / n) * i) * (Math.PI / 180);
    const r = 36; // percent, in the same 0-100 coordinate space as the SVG viewBox
    return { ...c, x: 50 + r * Math.cos(angle), y: 50 + r * Math.sin(angle) };
  });

  return (
    <div>
      <div className={`graph-wrap ${compact ? "graph-wrap-compact" : ""}`}>
        <svg className="graph-svg" viewBox="0 0 100 100">
          {positions.map((p, i) => {
            const isWinner = !mention.is_nil && p.qid === mention.qid;
            return (
              <line
                key={i}
                x1="50"
                y1="50"
                x2={p.x}
                y2={p.y}
                className={`graph-edge ${isWinner ? "graph-edge-winner" : ""}`}
                strokeWidth={0.6 + Math.min(p.confidence, 1) * 2.2}
                opacity={0.25 + Math.min(p.confidence, 1) * 0.65}
              />
            );
          })}
        </svg>

        <div className="graph-node graph-node-center" style={{ left: "50%", top: "50%" }}>
          <span className="graph-node-label">{mention.text}</span>
        </div>

        {positions.map((p, i) => {
          const isWinner = !mention.is_nil && p.qid === mention.qid;
          return (
            <div
              key={p.qid + i}
              className={`graph-node graph-node-candidate ${isWinner ? "graph-node-winner" : ""}`}
              style={{ left: `${p.x}%`, top: `${p.y}%` }}
              title={`${p.label} (${p.qid}) — semantic ${p.confidence.toFixed(3)}, popularity ${p.popularity} sitelinks (norm ${p.popularity_norm.toFixed(2)}), blended ${p.blended_score.toFixed(3)}. Source: ${SOURCE_LABELS[p.source] || p.source}`}
            >
              <span className="graph-node-label">{p.label}</span>
              <span className="graph-node-conf">{p.confidence.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
      {!compact && (
        <p className="muted small graph-hint">
          Edge thickness & opacity reflect embedding similarity to the mention's context.
          {!mention.is_nil && " The highlighted node is the linked entity."}
          {overflow > 0 && ` +${overflow} more candidate(s) in the Ranking tab.`}
        </p>
      )}
    </div>
  );
}

function SingleCandidateRow({ mention }) {
  // A mention with exactly one candidate has nothing to disambiguate — no
  // competing entity to rank against, so the circular graph layout is just
  // one lonely node in a lot of empty space. Show a flat mention -> entity
  // strip instead.
  const c = mention.candidates[0];
  return (
    <div className="single-cand-row">
      <span className="graph-node-label single-cand-chip">{mention.text}</span>
      <span className="single-cand-arrow">only candidate →</span>
      <span className="graph-node-label single-cand-chip single-cand-chip-winner">{c.label}</span>
      <span className="conf-value">{c.confidence.toFixed(2)}</span>
      <span className="source-badge">{SOURCE_LABELS[c.source] || c.source}</span>
    </div>
  );
}

function ScoreBreakdown({ mention, popularityWeight, nilThreshold }) {
  const rows = mention.candidates.slice(0, 6);
  return (
    <div className="score-breakdown">
      <div className="score-table-wrap">
        <table className="score-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Semantic</th>
              <th>Popularity</th>
              <th>Pop. norm</th>
              <th>Blended</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => {
              const isWinner = !mention.is_nil && c.qid === mention.qid;
              return (
                <tr key={c.qid + i} className={isWinner ? "score-row-winner" : ""}>
                  <td className="score-cand-name">
                    {c.label}
                    <span className="muted score-qid">{c.qid}</span>
                  </td>
                  <td>{c.confidence.toFixed(3)}</td>
                  <td>{c.popularity}</td>
                  <td>{c.popularity_norm.toFixed(2)}</td>
                  <td className="score-blended">{c.blended_score.toFixed(3)}</td>
                  <td className="score-source">{SOURCE_LABELS[c.source] || c.source}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small score-formula">
        blended = semantic + {popularityWeight.toFixed(2)} × pop.&nbsp;norm — ranking order is sorted by blended
        score, but a mention becomes <strong>NIL</strong> when the top candidate's raw semantic score falls below the{" "}
        {nilThreshold.toFixed(2)} threshold{mention.is_nil ? " (which happened here)." : "."}
      </p>
    </div>
  );
}

function explainWinner(mention) {
  const candidates = mention.candidates;
  if (!candidates || candidates.length === 0) return null;
  const winner = candidates[0];

  if (mention.is_nil) {
    return `No candidate was confident enough to link — the closest match, "${winner.label}", scored only ${winner.confidence.toFixed(
      2
    )} on semantic similarity to the context, below the NIL threshold.`;
  }
  if (candidates.length === 1) {
    return `"${winner.label}" was the only candidate found for this mention, so there was no ambiguity to resolve.`;
  }

  const runnerUp = candidates[1];
  const blendedGap = winner.blended_score - runnerUp.blended_score;
  const semanticOrderFlipped = winner.confidence < runnerUp.confidence;

  const reason = semanticOrderFlipped
    ? `the popularity tiebreak was decisive: "${runnerUp.label}" actually scored higher on raw semantic similarity (${runnerUp.confidence.toFixed(
        2
      )} vs ${winner.confidence.toFixed(2)}), but "${winner.label}"'s higher notability (${winner.popularity} Wikipedia editions vs ${
        runnerUp.popularity
      }) pushed it ahead`
    : `mainly semantic similarity to the context (${winner.confidence.toFixed(2)} vs ${runnerUp.confidence.toFixed(
        2
      )} for the runner-up, "${runnerUp.label}")`;

  return `"${winner.label}" beat the runner-up by ${blendedGap.toFixed(3)} blended points — ${reason}.`;
}

function WinnerExplanation({ mention }) {
  const text = explainWinner(mention);
  if (!text) return null;
  return <p className="winner-explanation">{text}</p>;
}

function MiniMap({ lat, lon }) {
  const d = 0.06;
  const bbox = `${lon - d},${lat - d},${lon + d},${lat + d}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat},${lon}`;
  return (
    <div className="mini-map-wrap">
      <iframe title="Location map" src={src} className="mini-map-iframe" loading="lazy" />
      <a
        href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=11/${lat}/${lon}`}
        target="_blank"
        rel="noreferrer"
        className="mini-map-link"
      >
        Open larger map <IconExternal />
      </a>
    </div>
  );
}

function EntityDetails({ mention, lang }) {
  const [tab, setTab] = useState("ranking");
  const [showAll, setShowAll] = useState(false);
  const [coordinates, setCoordinates] = useState(null);
  const [relations, setRelations] = useState(null);
  const [relationsLoading, setRelationsLoading] = useState(false);
  const [relationsQid, setRelationsQid] = useState(null);

  async function openRelationsTab() {
    setTab("relations");
    if (!mention || mention.is_nil) return;
    if (relationsQid === mention.qid) return; // already fetched for this entity
    setRelationsLoading(true);
    try {
      const data = await getRelations(mention.qid, lang);
      setRelations(data.relations);
      setCoordinates(data.coordinates);
      setRelationsQid(mention.qid);
    } catch {
      setRelations([]);
      setCoordinates(null);
    } finally {
      setRelationsLoading(false);
    }
  }

  if (!mention) {
    return (
      <div className="card details-card empty">
        <p className="muted">Run a query, then click a detected entity to see its details here.</p>
      </div>
    );
  }

  const meta = labelMeta(mention.label);
  const shown = showAll ? mention.candidates : mention.candidates.slice(0, 3);

  return (
    <div className="card details-card fade-in">
      <div className="details-header">
        <h2>Entity details</h2>
        {mention.wikidata_url && (
          <a href={mention.wikidata_url} target="_blank" rel="noreferrer" className="open-link">
            Open in Wikidata <IconExternal />
          </a>
        )}
      </div>

      <div className="details-identity">
        <div className={`avatar type-${mention.label}`}>
          <meta.Icon />
        </div>
        <div>
          <div className="details-name">{mention.is_nil ? mention.text : mention.entity_label}</div>
          <span className={`type-badge type-${mention.label}`}>{meta.name}</span>
        </div>
      </div>

      {mention.is_nil ? (
        <p className="muted nil-note">This mention could not be confidently linked to a Wikidata entity (NIL).</p>
      ) : (
        <>
          <div className="details-meta-row">
            <span className="muted">Wikidata ID</span>
            <a href={mention.wikidata_url} target="_blank" rel="noreferrer" className="qid-pill">
              {mention.qid} <IconExternal />
            </a>
          </div>
          {mention.entity_description && <p className="details-desc">{mention.entity_description}</p>}
        </>
      )}

      <WinnerExplanation mention={mention} />

      <div className="tabs">
        <button className={tab === "ranking" ? "active" : ""} onClick={() => setTab("ranking")}>
          Candidate ranking
        </button>
        <button className={tab === "metadata" ? "active" : ""} onClick={() => setTab("metadata")}>
          Metadata
        </button>
        {!mention.is_nil && (
          <button className={tab === "relations" ? "active" : ""} onClick={openRelationsTab}>
            Relations
          </button>
        )}
      </div>

      {tab === "ranking" &&
        (mention.candidates.length === 0 ? (
          <p className="muted">No candidates were found in the knowledge base for this mention.</p>
        ) : (
          <>
            <div className="ranking-list">
              {shown.map((c, i) => (
                <div className="ranking-row" key={c.qid + i}>
                  <span className="rank-num">{i + 1}</span>
                  <div className="ranking-info">
                    <div className="ranking-label">{c.label}</div>
                    <div className="ranking-qid">
                      {c.qid} · <span className="source-badge">{SOURCE_LABELS[c.source] || c.source}</span>
                    </div>
                  </div>
                  <div className="conf-bar-track small">
                    <div className="conf-bar-fill" style={{ width: `${Math.round(Math.min(c.confidence, 1) * 100)}%` }} />
                  </div>
                  <span className="conf-value">{c.confidence.toFixed(2)}</span>
                  {i === 0 && <span className="top-tag">Top</span>}
                </div>
              ))}
            </div>
            {mention.candidates.length > 3 && (
              <button className="view-all-btn" onClick={() => setShowAll(!showAll)}>
                {showAll ? "Show fewer" : `View all candidates (${mention.candidates.length})`}
              </button>
            )}
          </>
        ))}

      {tab === "metadata" && (
        <div className="metadata-list">
          <div>
            <span className="muted">Mention text</span>
            <span>{mention.text}</span>
          </div>
          <div>
            <span className="muted">Span</span>
            <span>
              {mention.start_char}–{mention.end_char}
            </span>
          </div>
          <div>
            <span className="muted">Entity type</span>
            <span>{meta.name}</span>
          </div>
          <div>
            <span className="muted">
              Confidence <InfoHint text={CONFIDENCE_HINT} />
            </span>
            <span>{mention.confidence.toFixed(3)}</span>
          </div>
        </div>
      )}

      {tab === "relations" &&
        (relationsLoading ? (
          <div className="skeleton-list">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : !coordinates && (!relations || relations.length === 0) ? (
          <p className="muted">No relations found for this entity.</p>
        ) : (
          <>
            {coordinates && <MiniMap lat={coordinates.lat} lon={coordinates.lon} />}
            {relations && relations.length > 0 && (
              <div className="metadata-list">
                {relations.map((r, i) => (
                  <div key={i}>
                    <span className="muted">{r.property}</span>
                    <a href={r.value_url} target="_blank" rel="noreferrer">
                      {r.value}
                    </a>
                  </div>
                ))}
              </div>
            )}
          </>
        ))}
    </div>
  );
}

export default function App() {
  const [lang, setLang] = useState("en");
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [phase, setPhase] = useState(-1);

  async function runQuery(queryText) {
    if (!queryText.trim()) return;
    setLoading(true);
    setError(null);
    setSelectedIdx(null);
    setPhase(0);

    const stepTimer = setInterval(() => {
      setPhase((p) => (p < 3 ? p + 1 : p));
    }, 350);

    try {
      const data = await linkText(lang, queryText);
      setResult(data);
      if (data.mentions.length) setSelectedIdx(0);
      setPhase(4);
    } catch (e) {
      setError(e.message);
      setPhase(-1);
    } finally {
      clearInterval(stepTimer);
      setLoading(false);
    }
  }

  const selectedMention = selectedIdx !== null && result ? result.mentions[selectedIdx] : null;

  return (
    <div className="page">
      <nav className="navbar">
        <div className="brand">
          <span className="brand-logo" />
          <div>
            <span className="brand-name">LinguaLink</span>
            <span className="brand-tag">Bridging languages. Connecting knowledge.</span>
          </div>
        </div>
        <div className="nav-links">
          <a href="#">Docs</a>
          <a href="#">GitHub</a>
          <a href="#">About</a>
        </div>
      </nav>

      <main className="container">
        <div className="hero-row">
          <div>
            <div className="eyebrow">MULTILINGUAL NLP</div>
            <h1>
              Multilingual <span className="accent">Entity Linking</span>
            </h1>
            <p className="subtitle">
              {PIPELINE_STEPS.map((s, i) => (
                <span key={s}>
                  {s}
                  {i < PIPELINE_STEPS.length - 1 && <span className="arrow"> → </span>}
                </span>
              ))}
            </p>
          </div>
          <div className="lang-pills">
            <IconGlobe className="globe-icon" />
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                className={`lang-pill ${lang === l.code ? "active" : ""}`}
                onClick={() => setLang(l.code)}
              >
                {l.name}
              </button>
            ))}
          </div>
        </div>

        <div className="grid">
          <div className="col-main">
            <div className="card">
              <div className="card-header-row">
                <h2>
                  <IconDoc /> Input text
                </h2>
                <button
                  className="text-btn"
                  onClick={() => {
                    setText("");
                    setResult(null);
                    setSelectedIdx(null);
                    setPhase(-1);
                  }}
                >
                  <IconTrash /> Clear
                </button>
              </div>
              <textarea
                rows={4}
                maxLength={500}
                placeholder="Paste a sentence to link its entities..."
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <div className="char-count">{text.length}/500</div>

              <div className="run-row">
                <button className="run-button" onClick={() => runQuery(text)} disabled={loading}>
                  {loading ? <span className="spinner" /> : <IconPlay />}
                  {loading ? "Running" : "Run analysis"}
                </button>
              </div>
              {(EXAMPLES[lang] || []).length > 0 && (
                <div className="examples">
                  {EXAMPLES[lang].map((ex, i) => (
                    <button
                      key={i}
                      className="example-chip"
                      onClick={() => {
                        setText(ex);
                        runQuery(ex);
                      }}
                    >
                      {ex.length > 55 ? ex.slice(0, 55) + "…" : ex}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {error && <p className="error">⚠ {error}</p>}

            {loading && !result && (
              <div className="card fade-in">
                <div className="skeleton-line" style={{ width: "40%", height: 14, marginBottom: 14 }} />
                <div className="skeleton-block" />
              </div>
            )}
            {loading && !result && (
              <div className="card fade-in">
                <div className="skeleton-line" style={{ width: "30%", height: 14, marginBottom: 14 }} />
                <div className="skeleton-row" />
                <div className="skeleton-row" />
              </div>
            )}

            {result && (
              <div className="card fade-in">
                <div className="card-header-row">
                  <div>
                    <h2>
                      <IconDoc /> Linked text
                    </h2>
                    <p className="muted small">Entities detected and linked to Wikidata</p>
                  </div>
                  <div className="legend">
                    {Object.entries(LABEL_META).map(([key, meta]) => (
                      <span key={key} className={`legend-item type-${key}`}>
                        <span className="legend-dot" /> {meta.name}
                      </span>
                    ))}
                  </div>
                </div>
                <p className="highlighted">
                  {highlightedText(result.text, result.mentions, selectedIdx, setSelectedIdx)}
                </p>
              </div>
            )}

            {result && (
              <div className="card fade-in">
                <h2>
                  <IconDoc /> Detected entities
                  <InfoHint text={CONFIDENCE_HINT} />
                </h2>
                {result.mentions.length === 0 ? (
                  <p className="muted">No entities detected in this text.</p>
                ) : (
                  <div className="entity-list">
                    {result.mentions.map((m, i) => {
                      const meta = labelMeta(m.label);
                      return (
                        <div
                          key={i}
                          className={`entity-row ${i === selectedIdx ? "selected" : ""}`}
                          onClick={() => setSelectedIdx(i)}
                        >
                          <div className={`avatar type-${m.label}`}>
                            <meta.Icon />
                          </div>
                          <div className="entity-row-main">
                            <div className="entity-row-name">
                              {m.is_nil ? m.text : m.entity_label}
                              <span className={`type-badge type-${m.label}`}>{meta.name}</span>
                            </div>
                            <div className="muted small">
                              {m.is_nil ? "Unlinkable" : `Wikidata: ${m.qid}`}
                            </div>
                          </div>
                          <div className="entity-row-conf">
                            <span className="muted small">Confidence</span>
                            <div className="conf-bar-track">
                              <div
                                className="conf-bar-fill"
                                style={{ width: `${Math.round(Math.min(m.confidence, 1) * 100)}%` }}
                              />
                            </div>
                          </div>
                          <span className="conf-value">{m.confidence.toFixed(2)}</span>
                          <IconChevron className="chevron" />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

          </div>

          <div className="col-side">
            <div className="card">
              <h2>
                <IconPipeline /> Processing pipeline
              </h2>
              <PipelineStepper phase={phase} />
            </div>

            <EntityDetails key={selectedIdx} mention={selectedMention} lang={lang} />
          </div>
        </div>

        {result && result.mentions.some((m) => m.candidates.length > 0) && (
          <div className="card fade-in graphs-section">
            <h2>
              <IconPipeline /> Disambiguation graphs
            </h2>
            <p className="muted small">
              One graph per detected mention, showing every candidate it was disambiguated against. blended =
              semantic + {result.popularity_weight.toFixed(2)} × pop.&nbsp;norm; a mention is NIL when its top
              candidate's raw semantic score is below {result.nil_threshold.toFixed(2)}.
            </p>
            <div className="graph-grid">
              {result.mentions.map((m, i) => {
                if (m.candidates.length === 0) return null;
                const meta = labelMeta(m.label);
                return (
                  <div
                    className={`graph-instance ${i === selectedIdx ? "graph-instance-selected" : ""}`}
                    key={i}
                    onClick={() => setSelectedIdx(i)}
                  >
                    <div className="graph-instance-title">
                      <span className={`type-badge type-${m.label}`}>{meta.name}</span>
                      {m.is_nil ? m.text : m.entity_label}
                    </div>
                    {m.candidates.length === 1 ? (
                      <SingleCandidateRow mention={m} />
                    ) : (
                      <DisambiguationGraph mention={m} compact maxCandidates={5} />
                    )}
                    <ScoreBreakdown
                      mention={m}
                      popularityWeight={result.popularity_weight}
                      nilThreshold={result.nil_threshold}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <footer className="footer">
          <span>LinguaLink · v0.1 · Built for open knowledge.</span>
          <span>Powered by Wikidata</span>
        </footer>
      </main>
    </div>
  );
}
