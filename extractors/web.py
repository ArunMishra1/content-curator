"""
Extracts clean article text from a webpage URL.

Why trafilatura and not "just parse the HTML with BeautifulSoup": a real article
page has navbars, ads, related-article widgets, comment sections, cookie banners.
BeautifulSoup gives you raw tags — you'd have to hand-write rules to strip all
that junk out. trafilatura is a library built specifically to solve "find the
main article content and discard the boilerplate." It's the right tool for
this specific job, not a generic HTML parser.
"""

import trafilatura
from models import ExtractedContent


def extract_article(url: str) -> ExtractedContent:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return ExtractedContent(
                url=url, title="", text="", source_type="article",
                error=f"Could not fetch URL (dead link, blocked, or timeout): {url}"
            )

        result = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            output_format="txt",
            with_metadata=True,
        )
        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata and metadata.title else url

        if not result or not result.strip():
            return ExtractedContent(
                url=url, title=title, text="", source_type="article",
                error="Page fetched but no extractable article text found (may be paywalled, JS-rendered, or not an article)."
            )

        return ExtractedContent(url=url, title=title, text=result, source_type="article")

    except Exception as e:
        # Catch-all is intentional here: this function runs in a batch ingest
        # loop. One bad URL should not crash the whole ingest job. We record
        # the error on the object and let the caller decide what to do with it.
        return ExtractedContent(
            url=url, title="", text="", source_type="article",
            error=f"Unexpected extraction error: {e}"
        )


def extract_from_html_string(url: str, html: str) -> ExtractedContent:
    """
    Testing/offline path: extract from raw HTML you already have, skipping the
    network fetch. Useful for unit tests and for this sandbox, where I can't
    reach arbitrary external URLs.
    """
    result = trafilatura.extract(html, include_comments=False, output_format="txt")
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata and metadata.title else url
    if not result or not result.strip():
        return ExtractedContent(url=url, title=title, text="", source_type="article",
                                 error="No extractable text in provided HTML.")
    return ExtractedContent(url=url, title=title, text=result, source_type="article")
