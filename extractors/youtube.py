"""
Extracts transcript text from a YouTube video URL.

Note the failure modes here are different from web articles: a video can have
transcripts disabled, be region-locked, or be auto-generated-only (lower
quality but still usable). We treat "no transcript available" as a normal,
expected failure — not a bug — because a meaningful fraction of YouTube videos
will hit this.
"""

import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from models import ExtractedContent


def _extract_video_id(url: str) -> str | None:
    """
    YouTube URLs come in several shapes:
      https://www.youtube.com/watch?v=VIDEO_ID
      https://youtu.be/VIDEO_ID
      https://www.youtube.com/embed/VIDEO_ID
    This normalizes all of them to just the video ID.
    """
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")

    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        match = re.match(r"/embed/([^/?]+)", parsed.path)
        if match:
            return match.group(1)

    return None


def extract_youtube(url: str) -> ExtractedContent:
    video_id = _extract_video_id(url)
    if not video_id:
        return ExtractedContent(
            url=url, title="", text="", source_type="youtube",
            error=f"Could not parse a video ID out of this URL: {url}"
        )

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join(segment["text"] for segment in transcript_list)

        if not full_text.strip():
            return ExtractedContent(
                url=url, title=video_id, text="", source_type="youtube",
                error="Transcript returned but was empty."
            )

        # We don't have the video title from the transcript API alone —
        # fetching it properly requires the YouTube Data API (needs its own
        # API key, a separate setup step). For now we use the video ID as a
        # placeholder title. Flagging this as a known gap, not hiding it.
        return ExtractedContent(url=url, title=f"YouTube video {video_id}", text=full_text, source_type="youtube")

    except TranscriptsDisabled:
        return ExtractedContent(url=url, title=video_id, text="", source_type="youtube",
                                 error="Transcripts are disabled for this video.")
    except NoTranscriptFound:
        return ExtractedContent(url=url, title=video_id, text="", source_type="youtube",
                                 error="No transcript found for this video (may not have captions).")
    except VideoUnavailable:
        return ExtractedContent(url=url, title=video_id, text="", source_type="youtube",
                                 error="Video is unavailable (private, deleted, or region-locked).")
    except Exception as e:
        return ExtractedContent(url=url, title=video_id, text="", source_type="youtube",
                                 error=f"Unexpected error fetching transcript: {e}")


def is_youtube_url(url: str) -> bool:
    hostname = urlparse(url).hostname or ""
    return "youtube.com" in hostname or "youtu.be" in hostname
