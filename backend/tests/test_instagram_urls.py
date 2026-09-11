"""Instagram URL normalization + rejection of non-profile paths."""
import pytest

from app.providers.instagram_url import (
    extract_handle,
    is_valid_profile_url,
    normalize_instagram_url,
)

VALID = [
    ("https://instagram.com/username", "username"),
    ("https://www.instagram.com/username/", "username"),
    ("http://instagram.com/username/", "username"),
    ("instagram.com/User.Name_1", "user.name_1"),
    ("https://www.instagram.com/neilpatel?hl=en", "neilpatel"),
    ("@janesmith", "janesmith"),
]

REJECT = [
    "https://www.instagram.com/p/DabcdEFGhij/",
    "https://www.instagram.com/reel/DabcdEFGhij/",
    "https://www.instagram.com/reels/audio/123/",
    "https://www.instagram.com/explore/tags/ai/",
    "https://www.instagram.com/explore/",
    "https://www.instagram.com/stories/someone/123/",
    "https://www.instagram.com/accounts/login/",
    "https://www.instagram.com/directory/profiles/",
    "https://www.instagram.com/developer/",
    "https://help.instagram.com/1164300158112141",
    "https://www.instagram.com/username/tagged/",
    "https://twitter.com/username",
    "https://www.instagram.com/",
    "not a url",
    "",
]


@pytest.mark.parametrize("url,handle", VALID)
def test_valid_profiles_extract_handle(url, handle):
    assert extract_handle(url) == handle
    assert is_valid_profile_url(url) is True


@pytest.mark.parametrize("url,handle", VALID)
def test_normalization_is_canonical(url, handle):
    assert normalize_instagram_url(url) == f"https://www.instagram.com/{handle}/"


@pytest.mark.parametrize("url", REJECT)
def test_non_profile_urls_rejected(url):
    assert extract_handle(url) is None
    assert is_valid_profile_url(url) is False
    assert normalize_instagram_url(url) is None
