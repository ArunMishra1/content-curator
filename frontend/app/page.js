"use client";

import { useState, useEffect, useRef } from "react";

export default function Home() {
  const [profile, setProfile] = useState("");
  const [topN, setTopN] = useState(5);
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  const [backendStatus, setBackendStatus] = useState("checking");

  const [ingestOpen, setIngestOpen] = useState(false);
  const [urlsText, setUrlsText] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestResults, setIngestResults] = useState(null);
  const [ingestError, setIngestError] = useState("");

  const [discoverQuery, setDiscoverQuery] = useState("");
  const [discovering, setDiscovering] = useState(false);
  const [discoverCandidates, setDiscoverCandidates] = useState(null);
  const [discoverError, setDiscoverError] = useState("");
  const [selectedCandidates, setSelectedCandidates] = useState(new Set());

  const ingestSectionRef = useRef(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => (res.ok ? setBackendStatus("online") : setBackendStatus("offline")))
      .catch(() => setBackendStatus("offline"));
  }, []);

  async function handleSearch(e) {
    e.preventDefault();
    if (!profile.trim()) return;

    setSearching(true);
    setSearchError("");
    setResults(null);

    try {
      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile, top_n: Number(topN) }),
      });
      const data = await res.json();

      if (!res.ok) {
        setSearchError(data.error || "Something went wrong reaching the backend.");
      } else {
        setResults(data.results || []);
      }
    } catch (err) {
      setSearchError("Couldn't reach the backend. Is it running on localhost:8000?");
    } finally {
      setSearching(false);
    }
  }

  async function handleIngest(e) {
    e.preventDefault();
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) return;

    setIngesting(true);
    setIngestError("");
    setIngestResults(null);

    try {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });
      const data = await res.json();

      if (!res.ok) {
        setIngestError(data.error || "Something went wrong reaching the backend.");
      } else {
        setIngestResults(data.results || []);
        setUrlsText("");
      }
    } catch (err) {
      setIngestError("Couldn't reach the backend. Is it running on localhost:8000?");
    } finally {
      setIngesting(false);
    }
  }

  async function handleDiscover(e, overrideQuery) {
    if (e) e.preventDefault();
    const q = overrideQuery ?? discoverQuery;
    if (!q.trim()) return;

    setDiscovering(true);
    setDiscoverError("");
    setDiscoverCandidates(null);
    setSelectedCandidates(new Set());

    try {
      const res = await fetch("/api/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, max_results: 10 }),
      });
      const data = await res.json();

      if (!res.ok) {
        setDiscoverError(data.error || "Something went wrong finding content.");
      } else {
        setDiscoverCandidates(data.results || []);
      }
    } catch (err) {
      setDiscoverError("Couldn't reach the backend. Is it running on localhost:8000?");
    } finally {
      setDiscovering(false);
    }
  }

  function discoverFromEmptyResults() {
    setDiscoverQuery(profile);
    setIngestOpen(true);
    handleDiscover(null, profile);
    // Give the ingest section a moment to actually open (React state update)
    // before scrolling to it, or the scroll target won't exist yet.
    setTimeout(() => {
      ingestSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  function toggleCandidate(url) {
    const next = new Set(selectedCandidates);
    if (next.has(url)) {
      next.delete(url);
    } else {
      next.add(url);
    }
    setSelectedCandidates(next);
  }

  function addSelectedToUrlList() {
    const urlsToAdd = Array.from(selectedCandidates);
    if (urlsToAdd.length === 0) return;

    setUrlsText((prev) => {
      const existing = prev.split("\n").map((u) => u.trim()).filter(Boolean);
      const combined = [...new Set([...existing, ...urlsToAdd])]; // dedupe against what's already typed
      return combined.join("\n");
    });

    // Clear discovery state after adding -- the URLs now live in the reviewable
    // textarea below, which is the single source of truth for what gets ingested.
    setDiscoverCandidates(null);
    setSelectedCandidates(new Set());
    setDiscoverQuery("");
  }

  function rankClass(index) {
    if (index === 0) return "rank-1";
    if (index === 1 || index === 2) return "rank-2";
    return "rank-rest";
  }

  return (
    <div className="page">
      <header className="header">
        <img src="/icon.svg" alt="" width="32" height="32" />
        <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 17 }}>
          content-curator
        </span>
        <span className={`status-dot ${backendStatus}`}>
          <span className="dot" />
          {backendStatus === "checking" ? "checking backend…" : backendStatus === "online" ? "backend online" : "backend unreachable"}
        </span>
      </header>

      <section className="hero">
        <h1>Who are you, and what do you need?</h1>
        <p>Describe the reader — role, goal, time available — and get content ranked for them specifically.</p>

        <form className="search-form" onSubmit={handleSearch}>
          <textarea
            className="profile-input"
            placeholder="e.g. VP of Engineering who needs to understand LLMs in 30 minutes"
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            rows={2}
          />
          <div className="search-row">
            <select className="top-n-select" value={topN} onChange={(e) => setTopN(e.target.value)}>
              {[3, 5, 10, 15, 20].map((n) => (
                <option key={n} value={n}>
                  top {n}
                </option>
              ))}
            </select>
            <button className="btn-primary" type="submit" disabled={searching || !profile.trim()}>
              {searching ? (
                <>
                  <span className="spinner" />
                  Reasoning…
                </>
              ) : (
                "Find content"
              )}
            </button>
          </div>
        </form>
      </section>

      {searchError && <div className="state-message error">{searchError}</div>}

      {results && results.length === 0 && !searchError && (
        <div className="state-message empty-with-action">
          <div>Nothing indexed matches this profile well yet.</div>
          <button className="btn-secondary" type="button" onClick={discoverFromEmptyResults} disabled={discovering}>
            {discovering ? "Searching the web…" : "Search the web for this"}
          </button>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="results">
          {results.map((r, i) => (
            <div key={r.doc_id} className={`result-card ${rankClass(i)}`}>
              <div className="result-top-row">
                <div className="result-title">{r.title}</div>
                <div className="result-score">{r.score?.toFixed(3)}</div>
              </div>
              {r.reason && <div className="result-reason">{r.reason}</div>}
              {r.summary && <div className="result-summary">{r.summary}</div>}
              <div className="result-footer">
                <span className="result-source-type">{r.source_type}</span>
                <a className="result-link" href={r.url} target="_blank" rel="noreferrer">
                  visit source →
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      <section className="ingest-section" ref={ingestSectionRef}>
        <button
          className={`ingest-toggle ${ingestOpen ? "open" : ""}`}
          onClick={() => setIngestOpen(!ingestOpen)}
          type="button"
        >
          <span className="chevron">▸</span>
          Add content to the index
        </button>

        {ingestOpen && (
          <div className="ingest-body">
            <div className="discover-block">
              <div className="discover-label">Find URLs for a topic (via Tavily search)</div>
              <form className="discover-form" onSubmit={handleDiscover}>
                <input
                  className="discover-input"
                  type="text"
                  placeholder="e.g. LLM architecture explainers"
                  value={discoverQuery}
                  onChange={(e) => setDiscoverQuery(e.target.value)}
                />
                <button className="btn-secondary" type="submit" disabled={discovering || !discoverQuery.trim()}>
                  {discovering ? "Searching…" : "Find URLs"}
                </button>
              </form>

              {discoverError && <div className="state-message error">{discoverError}</div>}

              {discoverCandidates && discoverCandidates.length === 0 && (
                <div className="state-message">No results found for that topic.</div>
              )}

              {discoverCandidates && discoverCandidates.length > 0 && (
                <>
                  <div className="discover-candidates">
                    {discoverCandidates.map((c) => (
                      <label key={c.url} className="discover-candidate">
                        <input
                          type="checkbox"
                          checked={selectedCandidates.has(c.url)}
                          onChange={() => toggleCandidate(c.url)}
                        />
                        <div className="discover-candidate-text">
                          <div className="discover-candidate-title">{c.title}</div>
                          <div className="discover-candidate-snippet">{c.snippet}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={addSelectedToUrlList}
                    disabled={selectedCandidates.size === 0}
                  >
                    Add {selectedCandidates.size > 0 ? selectedCandidates.size : ""} selected to URL list below
                  </button>
                </>
              )}
            </div>

            <textarea
              className="ingest-textarea"
              placeholder={"https://example.com/article-one\nhttps://youtube.com/watch?v=...\n(one URL per line)"}
              value={urlsText}
              onChange={(e) => setUrlsText(e.target.value)}
            />
            <div className="ingest-hint">One URL per line. Articles or YouTube videos. Summaries are generated automatically.</div>
            <button className="btn-secondary" onClick={handleIngest} disabled={ingesting || !urlsText.trim()}>
              {ingesting ? "Ingesting…" : "Ingest"}
            </button>

            {ingestError && <div className="state-message error">{ingestError}</div>}

            {ingestResults && (
              <div className="ingest-results">
                {ingestResults.map((r) => (
                  <div key={r.url} className={`ingest-result-row ${r.success ? "success" : "failure"}`}>
                    <span>{r.success ? "✓" : "✗"}</span>
                    <span className="url">{r.url}</span>
                    {!r.success && <span>{r.error}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
