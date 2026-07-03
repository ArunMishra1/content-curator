# Taxonomy: Capabilities, Roadmap, and Extension Patterns

## Contents

- [What this product can currently do](#what-this-product-can-currently-do)
- [What's planned](#whats-planned)
- [How to add a new content source pattern](#how-to-add-a-new-content-source-pattern)
- [Build history and design reasoning](#build-history-and-design-reasoning)

## What this product can currently do

**Content sources supported:**
- Web articles (any public webpage) — cleaned via `trafilatura`, boilerplate
  (nav, ads, comments) stripped automatically
- YouTube videos — transcript/caption text extracted directly, no video/audio
  processing

**Ingestion capabilities:**
- Deduplication by exact URL match (re-ingesting the same URL updates the
  existing entry rather than duplicating it)
- Batch ingestion — a single API call accepts multiple URLs, and one failure
  doesn't block the rest
- Per-document AI summary, generated once at ingest time
- Safe under concurrent ingestion of the same URL (no data corruption from
  simultaneous requests)

**Recommendation capabilities:**
- Free-text reader profile as input (e.g. "VP of Engineering who needs to
  understand LLMs in 30 minutes")
- Ranking by semantic similarity between the profile and content
- Returns whole documents (not fragments), each with title, URL, AI summary,
  and a relevance score
- Configurable result count (1-20)

**Operational capabilities:**
- API key authentication on write/query endpoints
- Rate limiting (different limits for expensive vs. cheap operations)
- Public health check endpoint

**What it does NOT do yet** (matching-relevant limitations, not just missing
features):
- Does not distinguish reading difficulty or professional relevance — see
  [TODO.md](TODO.md) for the active design work on this
- Does not classify content by topic/category — there's no taxonomy of
  content types beyond `article` vs `youtube` as a source-format label (not
  a subject-matter label)
- Does not handle PDFs, podcasts, Twitter/X threads, or any source type
  beyond the two listed above

## What's planned

Full detail lives in [TODO.md](TODO.md) — this section is the summary.

Actively being designed: profession/capability-aware ranking, so a "VP of
Engineering" profile and a "PhD researcher" profile asking about the same
topic get genuinely different, appropriately-pitched recommendations rather
than the same results ranked by topic overlap alone.

Backlogged: additional content source types, request coalescing for
duplicate concurrent ingests, per-user API keys, multi-instance-safe storage.

## How to add a new content source pattern

The system currently supports two source types (web articles, YouTube). If
you want to add a new one (PDFs, podcast transcripts, Twitter threads,
internal docs, etc.), here's the pattern to follow — modeled on how
`extractors/youtube.py` was added alongside `extractors/web.py`.

### 1. Write a detector function

A function that looks at a URL and returns `True`/`False` for whether this
extractor should handle it. See `is_youtube_url()` in
`extractors/youtube.py` for the pattern — usually just a hostname/path check.

### 2. Write the extractor

A function `extract_<sourcetype>(url: str) -> ExtractedContent` that:
- Fetches/accesses the content
- Cleans it into plain text
- Returns an `ExtractedContent` object (see `models.py`) with `ok=True` and
  the text on success, or `error` set on failure — never raises an
  exception for expected failure modes (dead link, no content, access
  denied, etc.). Reserve real exceptions for truly unexpected situations.

Look at `extractors/web.py` and `extractors/youtube.py` side by side — they
solve different fetching problems but return the identical shape, which is
exactly why `pipeline.py` doesn't need to know which one ran.

### 3. Wire it into the router

In `pipeline.py`'s `ingest_url()`, the line:
```python
extracted = extract_youtube(url) if is_youtube_url(url) else extract_article(url)
```
becomes a chain of checks — add your new detector/extractor pair here. If
you're adding a third or fourth source type, consider refactoring this into
a list of `(detector, extractor)` pairs checked in order, rather than an
ever-growing if/elif chain.

### 4. Add a source_type value

`ExtractedContent.source_type` and `Document.source_type` are free-text
strings today (`"article"`, `"youtube"`). Use a new short, consistent value
for your source type — this flows through to the API response so callers
can distinguish result types.

### 5. Write tests the same way existing ones are written

Don't require real network access or real API keys. See
`tests/test_pipeline.py` for the pattern of mocking `extract_article`/
`extract_youtube` — your new extractor should be equally mockable if it
follows the same function signature and return type.

### 6. Update the capabilities list above

Keep this file's "What this product can currently do" section honest and
current when you add a new source type — it's the single place meant to
answer "what can this actually handle right now."

## Build history and design reasoning

This file is about *capability* and *how to extend* — it deliberately does
NOT duplicate the project's build history or design rationale, since
maintaining the same information in two places means one of them silently
goes stale. For those:

- **What was built, when, and what bugs were found and fixed along the
  way** -> [CHANGELOG.md](CHANGELOG.md)
- **Why individual technical choices were made the way they were** ->
  [DESIGN.md](DESIGN.md)
- **Specific errors encountered and their actual fixes** ->
  [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
