"""Helpers shared by every artwork source."""

KNOWN_PLACEHOLDER_HASHES = (
    "2a96cbd8b46e442fc41c2b86b821562f",  # Default Last.fm star track/album image
    "c6f707e6e835197e0bdc2870105e35ed",  # Default Last.fm artist image
    "4128a60df9657d23539f78077e2f5763",  # Additional default image variant
)


def is_placeholder_artwork(url: str) -> bool:
    if not url:
        return True
    return any(placeholder in url for placeholder in KNOWN_PLACEHOLDER_HASHES)
