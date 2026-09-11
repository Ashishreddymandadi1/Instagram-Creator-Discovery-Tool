"""Instagram profile URL normalization, validation and handle extraction.

Explicitly rejects non-profile paths (posts, reels, explore, hashtags, login,
and Instagram's own marketing/hub pages) rather than relying on a loose regex.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# First path segment values that are never a profile handle.
RESERVED_SEGMENTS: frozenset[str] = frozenset(
    {
        "p", "reel", "reels", "explore", "stories", "story", "accounts", "direct",
        "about", "developer", "developers", "tv", "s", "web", "legal", "privacy",
        "help", "api", "session", "emails", "challenge", "oauth", "graphql",
        "ajax", "language", "topics", "locations", "lite", "igtv",
        # Instagram's own hubs / marketing pages — not creator profiles
        "creators", "business", "shop", "shopping", "directory", "blog", "press",
        "brand", "creator", "ads", "help", "about", "safety", "community",
        "enterprise", "partnerships", "reels_audio",
    }
)

# Instagram handles: letters, digits, period, underscore, 1–30 chars.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_HASHTAG_HINT = re.compile(r"(?:^|/)explore/tags/|/tags/|%23|#", re.IGNORECASE)


def _clean_host(host: str) -> str:
    return host.lower().removeprefix("www.").removeprefix("m.")


def extract_handle(url: str) -> str | None:
    """Return the lowercase handle (no @) for a valid IG *profile* URL, else None."""
    if not url or not isinstance(url, str):
        return None
    candidate = url.strip()
    if candidate.startswith("@"):  # bare "@handle"
        candidate = candidate[1:]
        return candidate.lower() if _HANDLE_RE.match(candidate) else None

    if "://" not in candidate:
        candidate = "https://" + candidate

    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None

    host = _clean_host(parsed.netloc)
    if host not in {"instagram.com", "instagr.am"}:
        return None

    if _HASHTAG_HINT.search(parsed.path) or _HASHTAG_HINT.search(parsed.query or ""):
        return None

    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return None

    first = segments[0].lower()
    if first in RESERVED_SEGMENTS:
        return None
    # A profile URL is exactly one segment: instagram.com/<handle>[/]
    if len(segments) > 1:
        return None
    if not _HANDLE_RE.match(segments[0]):
        return None
    if segments[0].replace(".", "").replace("_", "") == "":
        return None
    return segments[0].lower()


def is_valid_profile_url(url: str) -> bool:
    return extract_handle(url) is not None


def normalize_instagram_url(url: str) -> str | None:
    """Canonical form: https://www.instagram.com/<handle>/ ; None if not a profile."""
    handle = extract_handle(url)
    if handle is None:
        return None
    return f"https://www.instagram.com/{handle}/"


def handle_to_url(handle: str) -> str:
    h = handle.strip().lstrip("@").lower()
    return f"https://www.instagram.com/{h}/"
