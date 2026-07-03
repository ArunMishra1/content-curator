"""
Wraps ChromaDB. This is the one file that should know ChromaDB's API exists —
everything else in the pipeline talks to VectorStore's methods, not to Chroma
directly. Same reasoning as the embeddings abstraction: if you ever swap
vector databases (Pinecone, Qdrant, pgvector), this is the only file that changes.

Key design decision: we store one entry per CHUNK, not per document, because
that's what gets embedded and searched. But the user wants document-level
results ("top 5 content pieces"), not chunk-level results. So querying
involves two steps:
  1. Ask Chroma for the top-N matching chunks.
  2. Collapse those chunks back to their parent documents, keeping each
     document's BEST matching chunk score (not average — a document that
     has one extremely relevant paragraph should rank highly even if the
     rest of the document is about something else).

We also duplicate document-level metadata (title, url, summary) onto every
chunk. This is deliberate redundancy: it means a single query gets everything
needed to build the final response, with no second database lookup required.
At MVP scale (thousands of chunks, not millions), the storage cost of this
duplication is negligible compared to the simplicity it buys.
"""

from typing import List, Dict, Any, Optional
import chromadb
from embeddings import EmbeddingProvider
from models import Document


class VectorStore:
    def __init__(self, embedder: EmbeddingProvider, persist_directory: str = "./chroma_data", collection_name: str = "content"):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=persist_directory)
        # cosine similarity is the standard choice for text embeddings —
        # it measures direction (meaning) not magnitude (text length)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(self, document: Document) -> None:
        if not document.chunks:
            raise ValueError(f"Document {document.doc_id} has no chunks — nothing to store")

        texts = [c.text for c in document.chunks]
        vectors = self.embedder.embed(texts)

        ids = [c.chunk_id for c in document.chunks]
        metadatas = [
            {
                "doc_id": document.doc_id,
                "url": document.url,
                "title": document.title,
                "source_type": document.source_type,
                "summary": document.summary,
                "chunk_index": c.chunk_index,
            }
            for c in document.chunks
        ]

        # upsert, not add: re-ingesting the same URL should update it, not
        # create duplicate entries. Chroma's `add` would error on duplicate IDs;
        # `upsert` handles the re-ingest case cleanly.
        self.collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

    def query(self, profile_text: str, top_n_documents: int = 5, chunks_to_scan: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        chunks_to_scan controls how many raw chunk matches we pull before
        collapsing to documents. This MUST scale with how much is indexed:
        a document with many chunks (a long article) can otherwise fill
        every slot in a small fixed window, crowding out shorter but
        genuinely relevant documents entirely -- not just ranking them
        lower, but making them invisible. Confirmed in testing: a 181-chunk
        document crowded out a 12-chunk document at chunks_to_scan=30.

        If not specified, we scan generously relative to the index size
        (at least 300, or the whole collection if smaller). This is a
        blunt fix appropriate for MVP scale (hundreds to low thousands of
        chunks) -- it does not scale to a huge multi-tenant index, where
        the correct fix is a smarter per-document-capped search instead of
        widening the net.
        """
        total_chunks = self.count()
        if chunks_to_scan is None:
            chunks_to_scan = min(total_chunks, max(300, top_n_documents * 60))

        query_vector = self.embedder.embed([profile_text])[0]

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=chunks_to_scan,
            include=["metadatas", "distances", "documents"],
        )

        if not results["ids"][0]:
            return []

        # Collapse chunks to documents, keeping the best (lowest distance /
        # highest similarity) score per document.
        best_per_doc: Dict[str, Dict[str, Any]] = {}
        for metadata, distance, chunk_text in zip(
            results["metadatas"][0], results["distances"][0], results["documents"][0]
        ):
            doc_id = metadata["doc_id"]
            similarity = 1 - distance  # Chroma cosine distance -> similarity

            if doc_id not in best_per_doc or similarity > best_per_doc[doc_id]["score"]:
                best_per_doc[doc_id] = {
                    "doc_id": doc_id,
                    "url": metadata["url"],
                    "title": metadata["title"],
                    "source_type": metadata["source_type"],
                    "summary": metadata["summary"],
                    "score": round(similarity, 4),
                    "matched_chunk": chunk_text,
                }

        ranked = sorted(best_per_doc.values(), key=lambda d: d["score"], reverse=True)
        return ranked[:top_n_documents]

    def count(self) -> int:
        return self.collection.count()
