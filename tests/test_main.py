"""
Tests the FastAPI route wiring -- request validation, response shaping,
status codes, and auth enforcement -- without loading the real embedding
model or touching the network. We mock the pipeline functions main.py
depends on, and set a known test API key so authenticated requests can
actually be constructed.
"""

import os
os.environ["CURATOR_API_KEY"] = "test-key-for-unit-tests-only"

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from models import IngestResult

AUTH_HEADERS = {"X-API-Key": "test-key-for-unit-tests-only"}


def make_client():
    """
    Patches the model-loading calls BEFORE importing main, so the lifespan
    startup handler doesn't try to download the real embedding model.
    """
    with patch("pipeline.get_embedder", return_value=MagicMock()), \
         patch("pipeline.get_vectorstore", return_value=MagicMock()):
        import main
        return main, TestClient(main.app)


def test_ingest_requires_api_key():
    main, client = make_client()
    response = client.post("/ingest", json={"urls": ["https://example.com/a"]})
    assert response.status_code == 401, response.text
    assert "Missing" in response.json()["detail"]
    print("PASS: /ingest rejects requests with no API key")


def test_ingest_rejects_wrong_api_key():
    main, client = make_client()
    response = client.post(
        "/ingest",
        json={"urls": ["https://example.com/a"]},
        headers={"X-API-Key": "definitely-the-wrong-key"},
    )
    assert response.status_code == 401, response.text
    assert "Invalid" in response.json()["detail"]
    print("PASS: /ingest rejects requests with a wrong API key")


def test_recommend_requires_api_key():
    main, client = make_client()
    response = client.post("/recommend", json={"profile": "test", "top_n": 5})
    assert response.status_code == 401, response.text
    print("PASS: /recommend rejects requests with no API key")


def test_health_does_not_require_api_key():
    """
    /health is intentionally public -- monitoring tools and load balancers
    need to hit it without credentials, and it exposes nothing sensitive.
    """
    main, client = make_client()
    with patch("main.get_vectorstore") as mock_get_store:
        mock_get_store.return_value.count.return_value = 10
        response = client.get("/health")
    assert response.status_code == 200, response.text
    print("PASS: /health remains accessible without an API key")


def test_ingest_endpoint_shapes_response_correctly():
    main, client = make_client()
    fake_results = [
        IngestResult(url="https://example.com/a", success=True, doc_id="id1", title="Article A"),
        IngestResult(url="https://example.com/b", success=False, doc_id="id2", error="404 Not Found"),
    ]
    with patch("main.ingest_urls", return_value=fake_results):
        response = client.post(
            "/ingest",
            json={"urls": ["https://example.com/a", "https://example.com/b"]},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["succeeded"] == 1
    assert body["failed"] == 1
    assert body["results"][1]["error"] == "404 Not Found"
    print("PASS: /ingest correctly reports per-URL success/failure counts (with valid auth)")


def test_ingest_rejects_empty_url_list():
    main, client = make_client()
    response = client.post("/ingest", json={"urls": []}, headers=AUTH_HEADERS)
    assert response.status_code == 422, "Empty URL list should be rejected by validation, not reach the pipeline"
    print("PASS: /ingest rejects an empty URL list at the validation layer")


def test_recommend_endpoint_shapes_response_correctly():
    main, client = make_client()
    fake_store_results = [
        {"doc_id": "id1", "url": "https://example.com/a", "title": "LLM Basics",
         "source_type": "article", "summary": "Covers transformer basics.", "score": 0.87, "matched_chunk": "..."},
    ]
    fake_reranked = [
        {"doc_id": "id1", "url": "https://example.com/a", "title": "LLM Basics",
         "source_type": "article", "summary": "Covers transformer basics.", "score": 0.87,
         "reason": "Matches this reader's stated time constraint and expertise level."},
    ]
    with patch("main.get_vectorstore") as mock_get_store, \
         patch("main.rerank_for_profile", return_value=fake_reranked) as mock_rerank:
        mock_get_store.return_value.query.return_value = fake_store_results
        response = client.post(
            "/recommend",
            json={"profile": "VP of Engineering, 30 minutes on LLMs", "top_n": 5},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["title"] == "LLM Basics"
    assert body["results"][0]["score"] == 0.87
    assert body["results"][0]["reason"] == "Matches this reader's stated time constraint and expertise level."
    mock_rerank.assert_called_once()
    print("PASS: /recommend correctly shapes reranked results into the API response, including the reason field (with valid auth)")


def test_recommend_requests_broader_pool_than_top_n():
    """
    The reranker needs real choices to reason over -- if we only ever
    fetched top_n candidates from the vector store, the LLM would have
    nothing to actually rerank. Verify the candidate pool requested is
    larger than top_n.
    """
    main, client = make_client()
    with patch("main.get_vectorstore") as mock_get_store, \
         patch("main.rerank_for_profile", return_value=[]):
        mock_get_store.return_value.query.return_value = []
        client.post(
            "/recommend",
            json={"profile": "test profile", "top_n": 3},
            headers=AUTH_HEADERS,
        )
        call_kwargs = mock_get_store.return_value.query.call_args.kwargs
        requested_pool_size = call_kwargs.get("top_n_documents")

    assert requested_pool_size is not None and requested_pool_size > 3, (
        f"Expected candidate pool larger than top_n=3, got {requested_pool_size}"
    )
    print(f"PASS: /recommend requests a broader candidate pool ({requested_pool_size}) than the requested top_n (3)")


def test_recommend_rejects_empty_profile():
    main, client = make_client()
    response = client.post("/recommend", json={"profile": "", "top_n": 5}, headers=AUTH_HEADERS)
    assert response.status_code == 422, "Empty profile should be rejected by validation"
    print("PASS: /recommend rejects an empty profile string")


def test_recommend_rejects_out_of_range_top_n():
    main, client = make_client()
    response = client.post("/recommend", json={"profile": "test profile", "top_n": 100}, headers=AUTH_HEADERS)
    assert response.status_code == 422, "top_n above the allowed max (20) should be rejected"
    print("PASS: /recommend rejects an out-of-range top_n")


def test_health_endpoint():
    main, client = make_client()
    with patch("main.get_vectorstore") as mock_get_store:
        mock_get_store.return_value.count.return_value = 42
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["chunks_indexed"] == 42
    print("PASS: /health reports index size correctly")


def test_ingest_rate_limit_enforced():
    """
    /ingest is limited to 10/minute. This test calls it 11 times with valid
    auth and expects the 11th to be rejected with 429 -- proving the limit
    is real, not just present in code and never actually triggered.

    We reset the limiter's internal counters first because every test in
    this file authenticates with the SAME api key (there's only one valid
    key in this app's auth model), so without resetting, whatever quota
    earlier tests already used would eat into this test's budget and make
    it flaky depending on test execution order.
    """
    main, client = make_client()
    main.limiter.reset()

    with patch("main.ingest_urls", return_value=[]):
        statuses = []
        for _ in range(11):
            response = client.post("/ingest", json={"urls": ["https://example.com/a"]}, headers=AUTH_HEADERS)
            statuses.append(response.status_code)

    assert statuses[:10] == [200] * 10, f"Expected first 10 calls to succeed, got {statuses[:10]}"
    assert statuses[10] == 429, f"Expected 11th call to be rate-limited (429), got {statuses[10]}"
    print("PASS: /ingest enforces its 10/minute rate limit on the 11th call")


if __name__ == "__main__":
    test_ingest_requires_api_key()
    test_ingest_rejects_wrong_api_key()
    test_recommend_requires_api_key()
    test_health_does_not_require_api_key()
    test_ingest_endpoint_shapes_response_correctly()
    test_ingest_rejects_empty_url_list()
    test_recommend_endpoint_shapes_response_correctly()
    test_recommend_requests_broader_pool_than_top_n()
    test_recommend_rejects_empty_profile()
    test_recommend_rejects_out_of_range_top_n()
    test_health_endpoint()
    test_ingest_rate_limit_enforced()
    print("\nALL TESTS PASSED")
