"""
Tests discover.py's URL-discovery logic without a real Tavily API call.
Mocks the Tavily client, consistent with this project's testing philosophy
(see CONTRIBUTING.md) -- fast, free, no external dependency required to run.
"""

from unittest.mock import patch, MagicMock
import discover


def test_discover_returns_shaped_results():
    fake_response = {
        "results": [
            {"url": "https://example.com/a", "title": "Article A", "content": "Some content about the topic here."},
            {"url": "https://example.com/b", "title": "Article B", "content": "Different content about the topic."},
        ]
    }

    with patch("discover._get_client") as mock_get_client:
        mock_get_client.return_value.search.return_value = fake_response
        results = discover.discover_urls("test topic", max_results=10)

    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/a"
    assert results[0]["title"] == "Article A"
    assert results[0]["snippet"] == "Some content about the topic here."
    print("PASS: discover_urls correctly shapes Tavily results into url/title/snippet")


def test_discover_skips_malformed_results_without_crashing():
    """
    Defensive: if Tavily ever returns something malformed (no URL), skip
    that item rather than crash the whole request over one bad entry.
    """
    fake_response = {
        "results": [
            {"title": "Missing URL", "content": "no url field here"},
            {"url": "https://example.com/good", "title": "Good One", "content": "fine"},
        ]
    }

    with patch("discover._get_client") as mock_get_client:
        mock_get_client.return_value.search.return_value = fake_response
        results = discover.discover_urls("test topic")

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/good"
    print("PASS: discover_urls skips malformed results (missing URL) instead of crashing")


def test_discover_falls_back_to_url_when_title_missing():
    fake_response = {
        "results": [
            {"url": "https://example.com/no-title", "content": "some content"},
        ]
    }

    with patch("discover._get_client") as mock_get_client:
        mock_get_client.return_value.search.return_value = fake_response
        results = discover.discover_urls("test topic")

    assert results[0]["title"] == "https://example.com/no-title"
    print("PASS: discover_urls falls back to the URL itself when title is missing")


def test_discover_truncates_long_snippets():
    long_content = "x" * 1000
    fake_response = {
        "results": [{"url": "https://example.com/a", "title": "A", "content": long_content}]
    }

    with patch("discover._get_client") as mock_get_client:
        mock_get_client.return_value.search.return_value = fake_response
        results = discover.discover_urls("test topic")

    assert len(results[0]["snippet"]) <= 300
    print("PASS: discover_urls truncates long content to a preview-sized snippet")


def test_discover_missing_api_key_raises_clear_error():
    with patch.dict("os.environ", {}, clear=True):
        discover._client = None  # reset singleton so it re-checks the (now missing) env var
        try:
            discover.discover_urls("test topic")
            assert False, "Expected RuntimeError when TAVILY_API_KEY is not set"
        except RuntimeError as e:
            assert "TAVILY_API_KEY" in str(e)
            print("PASS: missing TAVILY_API_KEY raises a clear, specific error")


if __name__ == "__main__":
    test_discover_returns_shaped_results()
    test_discover_skips_malformed_results_without_crashing()
    test_discover_falls_back_to_url_when_title_missing()
    test_discover_truncates_long_snippets()
    test_discover_missing_api_key_raises_clear_error()
    print("\nALL TESTS PASSED")
