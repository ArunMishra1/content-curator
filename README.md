# AI Content Curator

Given a list of URLs, ingest and index their content. Given a reader profile
("VP of Engineering, 30 minutes on LLMs"), return the top 5 most relevant
pieces with a short summary of each.

## Status

Prototype / MVP. No auth, no multi-user support, single-node local vector
store. Built to prove the retrieval pipeline works — not production-ready.

## Architecture

```
URL --> extractor (web or YouTube) --> chunker --> embedder --> ChromaDB
                                          |
                                      summarizer (once, at ingest time)
```

- `embeddings.py` — abstraction over embedding backends. Currently local
  (sentence-transformers, free, no API key). Swappable to an API provider
  later without touching the rest of the pipeline.
- `extractors/web.py` — pulls clean article text from a webpage, stripping
  nav/ads/comments (via trafilatura).
- `extractors/youtube.py` — pulls video transcripts (via youtube-transcript-api).
- `chunking.py` — splits document text into overlapping ~500-char chunks
  for embedding.
- `summarizer.py` — generates a short summary per document, once, at ingest
  time (Claude Haiku). Never called at query time — that would be slow and
  expensive on every `/recommend` call.
- `models.py` — shared data shapes (ExtractedContent, Chunk, Document).

Still to build: `vectorstore.py` (ChromaDB wrapper), `pipeline.py`
(orchestrates the full ingest flow), `main.py` (FastAPI app).

## Known limitations (v1, accepted for now)

- Ranking is pure vector similarity between the profile text and content
  chunks. This matches on topic, not on reading difficulty or time budget —
  a highly technical paper can outrank a well-written primer on the same
  topic.
- YouTube video titles aren't fetched (would need a separate YouTube Data
  API key) — video ID is used as a placeholder title.
- No retry logic on failed URL fetches.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in your real ANTHROPIC_API_KEY
```

## Running tests

Each module has inline verification — see commit history / module docstrings
for example usage until a proper test suite is added.

## License

Apache 2.0 — see [LICENSE](LICENSE).
