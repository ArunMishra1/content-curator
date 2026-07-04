"""
Tests ranker.py's reasoning-reranking logic, without a real Anthropic API
call. We mock the client so this test is fast, free, and deterministic --
consistent with the rest of this project's testing philosophy (see
CONTRIBUTING.md).
"""

import json
from unittest.mock import patch, MagicMock
import ranker


def make_candidates(n):
    return [
        {
            "doc_id": f"doc{i}",
            "url": f"https://example.com/{i}",
            "title": f"Article {i}",
            "source_type": "article",
            "summary": f"Summary of article {i}.",
            "score": 1.0 - (i * 0.05),
        }
        for i in range(n)
    ]


def mock_llm_response(json_payload: str):
    """Builds a fake Anthropic response object matching the real SDK's shape."""
    mock_content_block = MagicMock()
    mock_content_block.text = json_payload
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]
    return mock_response


def test_rerank_reorders_per_llm_response():
    candidates = make_candidates(5)
    llm_output = json.dumps([
        {"doc_id": "doc3", "reason": "Best fit for this reader's stated goal."},
        {"doc_id": "doc0", "reason": "Good secondary option."},
    ])

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = mock_llm_response(llm_output)
        result = ranker.rerank_for_profile("test profile", candidates, top_n=2)

    assert len(result) == 2
    assert result[0]["doc_id"] == "doc3"
    assert result[0]["reason"] == "Best fit for this reader's stated goal."
    assert result[1]["doc_id"] == "doc0"
    print("PASS: reranker correctly reorders candidates per the LLM's response")


def test_rerank_drops_hallucinated_doc_ids():
    candidates = make_candidates(3)
    # "doc99" was never in the candidate pool -- the LLM should not be trusted here.
    llm_output = json.dumps([
        {"doc_id": "doc99", "reason": "Hallucinated pick."},
        {"doc_id": "doc1", "reason": "Real pick."},
    ])

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = mock_llm_response(llm_output)
        result = ranker.rerank_for_profile("test profile", candidates, top_n=5)

    doc_ids = [r["doc_id"] for r in result]
    assert "doc99" not in doc_ids, "Hallucinated doc_id should have been silently dropped"
    assert "doc1" in doc_ids
    print("PASS: reranker silently drops doc_ids the LLM hallucinated that weren't in the candidate pool")


def test_rerank_falls_back_on_api_failure():
    candidates = make_candidates(5)

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.side_effect = RuntimeError("ANTHROPIC_API_KEY not set")
        result = ranker.rerank_for_profile("test profile", candidates, top_n=3)

    assert len(result) == 3, "Should fall back to top-3 of original vector order"
    assert result[0]["doc_id"] == "doc0"  # original order preserved
    assert all(r["reason"] == "" for r in result), "Fallback results should have no LLM reason"
    print("PASS: reranker falls back to vector-similarity order when the LLM call fails")


def test_rerank_falls_back_on_unparseable_response():
    candidates = make_candidates(4)

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = mock_llm_response("not valid json at all")
        result = ranker.rerank_for_profile("test profile", candidates, top_n=2)

    assert len(result) == 2
    assert result[0]["doc_id"] == "doc0"
    print("PASS: reranker falls back gracefully when the LLM response isn't valid JSON")


def test_rerank_can_return_fewer_than_top_n():
    """
    If the LLM genuinely finds fewer good matches than top_n, the result
    should NOT be padded with weak picks just to hit the requested count.
    """
    candidates = make_candidates(5)
    llm_output = json.dumps([{"doc_id": "doc2", "reason": "Only genuinely good fit."}])

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = mock_llm_response(llm_output)
        result = ranker.rerank_for_profile("test profile", candidates, top_n=5)

    assert len(result) == 1, f"Expected exactly 1 result (no padding), got {len(result)}"
    print("PASS: reranker does not pad results with weak matches to reach top_n")


def test_rerank_respects_max_candidates_cap():
    candidates = make_candidates(50)  # far more than MAX_CANDIDATES

    with patch("ranker._get_client") as mock_get_client:
        mock_get_client.return_value.messages.create.return_value = mock_llm_response("[]")
        ranker.rerank_for_profile("test profile", candidates, top_n=5)
        call_args = mock_get_client.return_value.messages.create.call_args
        prompt_sent = call_args.kwargs["messages"][0]["content"]

    # Count how many candidate lines actually made it into the prompt
    sent_count = sum(1 for c in candidates if c["doc_id"] in prompt_sent)
    assert sent_count <= ranker.MAX_CANDIDATES, (
        f"Expected at most {ranker.MAX_CANDIDATES} candidates in the prompt, found {sent_count} -- cost control is not working"
    )
    print(f"PASS: candidate pool capped at {ranker.MAX_CANDIDATES} regardless of input size (bounds cost)")


def test_rerank_empty_candidates_returns_empty():
    result = ranker.rerank_for_profile("test profile", [], top_n=5)
    assert result == []
    print("PASS: reranking an empty candidate list returns an empty list without erroring")


if __name__ == "__main__":
    test_rerank_reorders_per_llm_response()
    test_rerank_drops_hallucinated_doc_ids()
    test_rerank_falls_back_on_api_failure()
    test_rerank_falls_back_on_unparseable_response()
    test_rerank_can_return_fewer_than_top_n()
    test_rerank_respects_max_candidates_cap()
    test_rerank_empty_candidates_returns_empty()
    print("\nALL TESTS PASSED")
