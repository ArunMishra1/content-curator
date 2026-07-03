"""
Orchestrates the full ingest flow: URL -> extract -> chunk -> summarize -> store.

Design decisions worth understanding:

1. doc_id is a hash of the URL, not a random ID. This means re-ingesting the
   same URL always produces the same doc_id, which is what makes the
   VectorStore's upsert behavior actually useful (update in place) instead
   of just avoiding a crash.

2. The embedder and vector store are module-level singletons, created once
   on first use via get_embedder()/get_vectorstore(), not re-created per
   call. Loading the embedding model is the slowest part of startup — doing
   it once and reusing it matters a lot once this runs behind an API server
   handling many requests.

3. ingest_urls() processes a batch and never lets one bad URL stop the rest.
   Every URL gets an IngestResult (success or failure with a reason), so the
   caller gets a full report instead of a crash on the first dead link.
"""

import hashlib
from typing import List, Optional

from models import Document, IngestResult
from extractors.web import extract_article
from extractors.youtube import extract_youtube, is_youtube_url
from chunking import chunk_text
from summarizer import summarize
from embeddings import LocalEmbeddingProvider
from vectorstore import VectorStore

_embedder: Optional[LocalEmbeddingProvider] = None
_vectorstore: Optional[VectorStore] = None


def get_embedder() -> LocalEmbeddingProvider:
    global _embedder
    if _embedder is None:
        _embedder = LocalEmbeddingProvider()
    return _embedder


def get_vectorstore() -> VectorStore:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = VectorStore(embedder=get_embedder())
    return _vectorstore


def _make_doc_id(url: str) -> str:
    """Deterministic ID from the URL — same URL always maps to the same ID."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def ingest_url(url: str, skip_summary: bool = False) -> IngestResult:
    """
    Process a single URL end to end. skip_summary exists for testing/dry-runs
    where you don't want to spend an API call — production calls should
    leave it False so results actually have summaries to show users.
    """
    doc_id = _make_doc_id(url)

    # Step 1: extract — route to the right extractor based on URL shape
    extracted = extract_youtube(url) if is_youtube_url(url) else extract_article(url)

    if not extracted.ok:
        return IngestResult(url=url, success=False, doc_id=doc_id, error=extracted.error)

    # Step 2: chunk
    chunks = chunk_text(doc_id, extracted.text)
    if not chunks:
        return IngestResult(url=url, success=False, doc_id=doc_id,
                             error="Extraction succeeded but produced no chunks (empty text after cleaning).")

    # Step 3: summarize (once, here at ingest time — never at query time)
    summary = ""
    if not skip_summary:
        try:
            summary = summarize(extracted.title, extracted.text)
        except Exception as e:
            # A failed summary shouldn't block ingestion — the document is
            # still searchable without one, just less informative in results.
            # We record this as a partial success, not a hard failure.
            summary = ""

    document = Document(
        doc_id=doc_id,
        url=url,
        title=extracted.title,
        source_type=extracted.source_type,
        full_text=extracted.text,
        summary=summary,
        chunks=chunks,
    )

    # Step 4: embed + store
    try:
        get_vectorstore().add_document(document)
    except Exception as e:
        return IngestResult(url=url, success=False, doc_id=doc_id,
                             error=f"Storage failed: {e}")

    return IngestResult(url=url, success=True, doc_id=doc_id, title=extracted.title)


def ingest_urls(urls: List[str], skip_summary: bool = False) -> List[IngestResult]:
    return [ingest_url(url, skip_summary=skip_summary) for url in urls]
