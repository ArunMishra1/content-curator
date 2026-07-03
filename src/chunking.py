"""
Splits a document's full text into overlapping chunks for embedding.

Why chunk at all, instead of embedding the whole document as one vector?
Embedding models compress text into a fixed-size vector. Compress a whole
5,000-word article into one vector and you lose most of the detail — it
becomes a vague "average" of everything the article covers. Compress a single
paragraph and the vector captures that paragraph's specific meaning much more
precisely. Since we're matching a specific user query against content, precision
per-chunk matters more than a single global summary vector.
"""

from typing import List
from models import Chunk

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def chunk_text(doc_id: str, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size, or chunks would never advance")

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_str = text[start:end]

        # Avoid cutting mid-word at the boundary: extend to the next space,
        # unless we're already at the end of the text.
        if end < len(text):
            last_space = chunk_str.rfind(" ")
            if last_space > chunk_size * 0.5:  # only adjust if it doesn't shrink the chunk too much
                chunk_str = chunk_str[:last_space]
                end = start + last_space

        chunk_str = chunk_str.strip()
        if chunk_str:
            chunks.append(Chunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}_chunk_{index}",
                text=chunk_str,
                chunk_index=index,
            ))
            index += 1

        start = end - overlap  # step forward, but re-cover the overlap region

    return chunks
