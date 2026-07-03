"""
Tests pipeline.py's orchestration logic — doc_id generation, batch handling,
partial-failure isolation — without touching the network, the embedding
model, or the Anthropic API. We mock extraction and summarization so this
test is fast, free, and runs anywhere, and so it tests OUR wiring logic
specifically, not the libraries underneath it.
"""

from unittest.mock import patch
from models import ExtractedContent
import pipeline


def test_doc_id_is_deterministic():
    id1 = pipeline._make_doc_id("https://example.com/article")
    id2 = pipeline._make_doc_id("https://example.com/article")
    id3 = pipeline._make_doc_id("https://example.com/different-article")
    assert id1 == id2, "Same URL must produce the same doc_id"
    assert id1 != id3, "Different URLs must produce different doc_ids"
    print("PASS: doc_id generation is deterministic per URL")


def test_ingest_handles_extraction_failure():
    with patch("pipeline.extract_article") as mock_extract, \
         patch("pipeline.is_youtube_url", return_value=False):
        mock_extract.return_value = ExtractedContent(
            url="https://example.com/dead", title="", text="", source_type="article",
            error="Could not fetch URL (dead link, blocked, or timeout)"
        )
        result = pipeline.ingest_url("https://example.com/dead")

    assert result.success is False
    assert "Could not fetch" in result.error
    print("PASS: extraction failure is reported cleanly, not raised as an exception")


def test_ingest_batch_isolates_failures():
    """
    The core promise of ingest_urls: one bad URL in a batch of three
    should not prevent the other two from succeeding.
    """
    good_content = ExtractedContent(
        url="https://example.com/good", title="Good Article",
        text="This is a perfectly good article with enough content to chunk properly for testing purposes here.",
        source_type="article"
    )
    bad_content = ExtractedContent(
        url="https://example.com/bad", title="", text="", source_type="article",
        error="404 Not Found"
    )

    def fake_extract(url):
        return bad_content if "bad" in url else good_content

    with patch("pipeline.extract_article", side_effect=fake_extract), \
         patch("pipeline.is_youtube_url", return_value=False), \
         patch("pipeline.get_vectorstore") as mock_get_store:

        mock_store = mock_get_store.return_value
        mock_store.add_document.return_value = None

        urls = [
            "https://example.com/good1",
            "https://example.com/bad",
            "https://example.com/good2",
        ]
        results = pipeline.ingest_urls(urls, skip_summary=True)

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    assert len(results) == 3, "Every URL must get a result, even failed ones"
    assert len(successes) == 2, f"Expected 2 successes, got {len(successes)}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"
    assert failures[0].url == "https://example.com/bad"
    print("PASS: batch ingest isolates one failure without affecting other URLs")


def test_skip_summary_avoids_llm_call():
    good_content = ExtractedContent(
        url="https://example.com/good", title="Good Article",
        text="Enough content here to form at least one chunk for the test to proceed correctly.",
        source_type="article"
    )

    with patch("pipeline.extract_article", return_value=good_content), \
         patch("pipeline.is_youtube_url", return_value=False), \
         patch("pipeline.summarize") as mock_summarize, \
         patch("pipeline.get_vectorstore") as mock_get_store:

        mock_get_store.return_value.add_document.return_value = None
        result = pipeline.ingest_url("https://example.com/good", skip_summary=True)

    assert result.success is True
    mock_summarize.assert_not_called()
    print("PASS: skip_summary=True correctly avoids calling the summarizer (no wasted API cost)")


def test_summary_failure_does_not_block_ingestion():
    """
    If the Anthropic API call fails (rate limit, bad key, network blip),
    the document should still be ingested and searchable -- just without
    a summary -- rather than the whole ingestion failing.
    """
    good_content = ExtractedContent(
        url="https://example.com/good", title="Good Article",
        text="Enough content here to form at least one chunk for the test to proceed correctly.",
        source_type="article"
    )

    with patch("pipeline.extract_article", return_value=good_content), \
         patch("pipeline.is_youtube_url", return_value=False), \
         patch("pipeline.summarize", side_effect=RuntimeError("ANTHROPIC_API_KEY not set")), \
         patch("pipeline.get_vectorstore") as mock_get_store:

        mock_get_store.return_value.add_document.return_value = None
        result = pipeline.ingest_url("https://example.com/good", skip_summary=False)

    assert result.success is True, "A summarizer failure should not fail the whole ingest"
    print("PASS: summarizer failure degrades gracefully instead of blocking ingestion")


if __name__ == "__main__":
    test_doc_id_is_deterministic()
    test_ingest_handles_extraction_failure()
    test_ingest_batch_isolates_failures()
    test_skip_summary_avoids_llm_call()
    test_summary_failure_does_not_block_ingestion()
    print("\nALL TESTS PASSED")
