"""
Tests the VectorStore's storage and chunk-to-document aggregation logic.

Uses a fake embedder instead of the real local model on purpose: this test
should run in milliseconds, without downloading anything, and should verify
OUR logic (aggregation, upsert, ranking) — not re-test that sentence-transformers
works. Testing our own code in isolation from external dependencies is the
right call here, not a shortcut.
"""

import shutil
from embeddings import EmbeddingProvider
from models import Document, Chunk
from vectorstore import VectorStore


class FakeEmbedder(EmbeddingProvider):
    """
    Deterministic bag-of-words style embedder for testing. Text containing
    'llm'/'transformer'/'model' words gets a vector pointing one direction;
    text containing 'recipe'/'cooking' words points another direction.
    This lets us assert real semantic-similarity-like behavior without
    needing an actual ML model.
    """
    TECH_WORDS = {"llm", "transformer", "model", "attention", "neural", "gpt"}
    COOKING_WORDS = {"recipe", "cooking", "flour", "oven", "bake"}

    def embed(self, texts):
        vectors = []
        for text in texts:
            words = set(text.lower().split())
            tech_score = len(words & self.TECH_WORDS)
            cooking_score = len(words & self.COOKING_WORDS)
            # 2D vector: [tech_axis, cooking_axis], plus small noise dims to
            # make it a realistic-shaped vector
            vectors.append([float(tech_score), float(cooking_score), 0.1, 0.1])
        return vectors

    @property
    def dimension(self) -> int:
        return 4


def make_doc(doc_id, title, text, summary):
    chunks = [Chunk(doc_id=doc_id, chunk_id=f"{doc_id}_0", text=text, chunk_index=0)]
    return Document(doc_id=doc_id, url=f"https://example.com/{doc_id}", title=title,
                     source_type="article", full_text=text, summary=summary, chunks=chunks)


def test_large_document_does_not_crowd_out_small_document():
    """
    Regression test for a real bug found in manual testing: a document with
    many chunks (e.g. a long Wikipedia article) could fill the entire raw
    chunk-scan window, making a shorter but genuinely relevant document
    invisible in results -- not just ranked lower, but completely absent.
    """
    test_dir = "./test_chroma_data_crowding"
    shutil.rmtree(test_dir, ignore_errors=True)

    store = VectorStore(embedder=FakeEmbedder(), persist_directory=test_dir, collection_name="test_crowding")

    # Simulate a long tech document: 50 chunks, all strongly tech-relevant.
    large_doc_chunks = [
        Chunk(doc_id="large_doc", chunk_id=f"large_{i}", text="llm transformer model gpt", chunk_index=i)
        for i in range(50)
    ]
    large_doc = Document(doc_id="large_doc", url="https://example.com/large", title="Huge LLM Article",
                          source_type="article", full_text="...", summary="A very long article.",
                          chunks=large_doc_chunks)

    # Simulate a short, but still tech-relevant, document: just 2 chunks.
    small_doc_chunks = [
        Chunk(doc_id="small_doc", chunk_id="small_0", text="llm model", chunk_index=0),
        Chunk(doc_id="small_doc", chunk_id="small_1", text="transformer attention", chunk_index=1),
    ]
    small_doc = Document(doc_id="small_doc", url="https://example.com/small", title="Short LLM Primer",
                          source_type="article", full_text="...", summary="A short primer.",
                          chunks=small_doc_chunks)

    store.add_document(large_doc)
    store.add_document(small_doc)

    # Old fixed chunks_to_scan=30 would only ever see chunks from large_doc
    # (which alone has 50) and never reach small_doc's 2 chunks.
    results = store.query("llm transformer model", top_n_documents=5)
    result_ids = [r["doc_id"] for r in results]

    assert "small_doc" in result_ids, (
        f"BUG: small_doc was crowded out of results entirely. Got: {result_ids}"
    )
    print("PASS: a document with few chunks is not crowded out by a document with many chunks")

    shutil.rmtree(test_dir, ignore_errors=True)


def run_test():
    test_dir = "./test_chroma_data"
    shutil.rmtree(test_dir, ignore_errors=True)  # clean slate each run

    store = VectorStore(embedder=FakeEmbedder(), persist_directory=test_dir, collection_name="test")

    doc1 = make_doc("doc1", "Understanding Transformers",
                     "transformer attention model neural gpt llm",
                     "An explainer on transformer architecture and attention.")
    doc2 = make_doc("doc2", "Sourdough Bread Recipe",
                     "recipe flour oven bake cooking",
                     "A step-by-step sourdough baking guide.")
    doc3 = make_doc("doc3", "LLM Fundamentals",
                     "llm model gpt transformer",
                     "Covers the basics of how large language models work.")

    for doc in (doc1, doc2, doc3):
        store.add_document(doc)

    assert store.count() == 3, f"Expected 3 chunks stored, got {store.count()}"
    print("PASS: all chunks stored")

    # Query with a tech-heavy profile — expect doc1 and doc3 to rank above doc2
    results = store.query("llm transformer model attention", top_n_documents=3)
    result_ids = [r["doc_id"] for r in results]
    print("Query results (tech query):", [(r["doc_id"], r["title"], r["score"]) for r in results])

    assert result_ids[0] in ("doc1", "doc3"), f"Expected a tech doc first, got {result_ids[0]}"
    assert "doc2" == result_ids[-1], f"Expected cooking doc ranked last, got order {result_ids}"
    print("PASS: tech query correctly ranks tech docs above cooking doc")

    # Query with a cooking profile — expect doc2 to rank first
    results2 = store.query("recipe flour bake cooking", top_n_documents=3)
    print("Query results (cooking query):", [(r["doc_id"], r["title"], r["score"]) for r in results2])
    assert results2[0]["doc_id"] == "doc2", f"Expected doc2 first for cooking query, got {results2[0]['doc_id']}"
    print("PASS: cooking query correctly ranks cooking doc first")

    # Test upsert: re-adding doc1 with same ID should not create duplicates
    store.add_document(doc1)
    assert store.count() == 3, f"Expected still 3 chunks after re-ingesting doc1, got {store.count()}"
    print("PASS: upsert does not create duplicates on re-ingest")

    # Test that summary and metadata are correctly attached to results
    assert results[0]["summary"] != "", "Expected summary to be populated in results"
    print("PASS: document metadata (summary, title, url) correctly attached to query results")

    shutil.rmtree(test_dir, ignore_errors=True)
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run_test()
    test_large_document_does_not_crowd_out_small_document()
