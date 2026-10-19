import asyncio
from typing import Optional

from src.domain.interfaces.artwork_provider import ArtworkProvider
from src.infrastructure.providers.deezer_client import DeezerArtworkProvider
from src.infrastructure.providers.musicbrainz_client import MusicBrainzArtworkProvider
from config.logging_config import get_logger


logger = get_logger(__name__)


class CandidateArtworkService:
    """Resolves all available artwork candidates for a track.

    Used by the customization window so the user can preview and choose
    between the Last.fm base image, Deezer and MusicBrainz.
    """

    def __init__(
        self,
        deezer_provider: Optional[ArtworkProvider] = None,
        musicbrainz_provider: Optional[ArtworkProvider] = None,
    ) -> None:
        self._deezer = deezer_provider or DeezerArtworkProvider()
        self._musicbrainz = musicbrainz_provider or MusicBrainzArtworkProvider()

    async def get_candidates(
        self,
        artist: str,
        title: str,
        album: str = "",
        base_url: str = "",
    ) -> dict[str, Optional[str]]:
        if not artist or not title:
            return {"base": base_url or None, "deezer": None, "musicbrainz": None}

        deezer_result, musicbrainz_result = await asyncio.gather(
            self._deezer.get_artwork_url(artist, title, album),
            self._musicbrainz.get_artwork_url(artist, title, album),
            return_exceptions=True,
        )

        if isinstance(deezer_result, Exception):
            logger.warning(f"Deezer candidate lookup failed: {deezer_result}")
            deezer_result = None
        if isinstance(musicbrainz_result, Exception):
            logger.warning(f"MusicBrainz candidate lookup failed: {musicbrainz_result}")
            musicbrainz_result = None

        return {
            "base": base_url or None,
            "deezer": deezer_result,
            "musicbrainz": musicbrainz_result,
        }

    async def close(self) -> None:
        await asyncio.gather(
            self._deezer.close(),
            self._musicbrainz.close(),
            return_exceptions=True,
        )
