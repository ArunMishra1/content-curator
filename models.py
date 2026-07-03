"""
Shared data shapes used across the pipeline. Defining these once, in one place,
means every module (extractor, chunker, summarizer, store) agrees on what a
"piece of content" looks like. Without this, you end up with dicts that have
slightly different keys in different files, and bugs that only show up at
runtime.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedContent:
    """Output of the extraction layer — one per URL, before chunking."""
    url: str
    title: str
    text: str
    source_type: str  # "article" or "youtube"
    error: Optional[str] = None  # set if extraction failed; text will be empty

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip())


@dataclass
class Chunk:
    """A slice of a document, ready to be embedded."""
    doc_id: str          # which document this chunk belongs to
    chunk_id: str        # unique id for this specific chunk
    text: str
    chunk_index: int      # position within the document (0, 1, 2...)


@dataclass
class IngestResult:
    """Outcome of ingesting a single URL — used to build a batch ingest report."""
    url: str
    success: bool
    doc_id: str = ""
    title: str = ""
    error: str = ""


@dataclass
class Document:
    """A fully processed document, ready to be stored and later retrieved."""
    doc_id: str
    url: str
    title: str
    source_type: str
    full_text: str
    summary: str = ""
    chunks: list = field(default_factory=list)  # list[Chunk]
