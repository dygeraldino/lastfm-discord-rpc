from dataclasses import replace
from typing import Optional

from src.domain.entities.track import Track
from src.domain.interfaces.music_provider import MusicProvider
from src.domain.interfaces.song_override_repository import SongOverrideRepository
from config.logging_config import get_logger


logger = get_logger(__name__)


class OverrideAwareMusicProvider(MusicProvider):
    """Decorator that applies per-track artwork overrides.

    The wrapped provider keeps its normal behaviour; when the user saved an
    override for the current artist/title, its artwork URL wins.
    """

    def __init__(self, inner: MusicProvider, overrides: SongOverrideRepository) -> None:
        self._inner = inner
        self._overrides = overrides

    async def get_current_track(self) -> Optional[Track]:
        track = await self._inner.get_current_track()
        if track is None:
            return None

        override = self._overrides.get(track.artist, track.title)
        if override:
            if override.source == "none":
                logger.debug(
                    f"Applying artwork override (none) for {track.display_name}"
                )
                return replace(track, artwork_url=None)
            if override.url:
                logger.debug(
                    f"Applying artwork override ({override.source}) for {track.display_name}"
                )
                return replace(track, artwork_url=override.url)

        return track

    async def close(self) -> None:
        await self._inner.close()
