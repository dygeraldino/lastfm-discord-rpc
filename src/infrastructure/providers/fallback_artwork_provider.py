from typing import Optional

from src.domain.interfaces.artwork_provider import ArtworkProvider
from src.infrastructure.persistence.json_artwork_cache_repository import JsonArtworkCacheRepository
from src.infrastructure.providers.deezer_client import DeezerArtworkProvider
from src.infrastructure.providers.musicbrainz_client import MusicBrainzArtworkProvider
from config.logging_config import get_logger

logger = get_logger(__name__)


class FallbackArtworkProvider(ArtworkProvider):
    """Composite artwork provider combining local JSON cache, Deezer API (primary),
    and MusicBrainz + Cover Art Archive (secondary).

    Lookup order:
      1. Local JSON cache (instant, no network)
      2. Deezer API (primary) — CDN URLs work with Discord Rich Presence
      3. MusicBrainz + Cover Art Archive (secondary)
      4. Cache negative result to avoid repeated lookups
    """

    def __init__(
        self,
        cache: JsonArtworkCacheRepository | None = None,
        deezer_provider: ArtworkProvider | None = None,
        musicbrainz_provider: ArtworkProvider | None = None,
    ) -> None:
        self._cache = cache or JsonArtworkCacheRepository()
        self._deezer = deezer_provider or DeezerArtworkProvider()
        self._musicbrainz = musicbrainz_provider or MusicBrainzArtworkProvider(cache=self._cache)

    async def get_artwork_url(self, artist: str, title: str, album: str = "") -> Optional[str]:
        if not artist or not title:
            return None

        # 1. Check local persistent cache
        is_cached, cached_url = self._cache.get_entry(artist, title)
        if is_cached:
            if cached_url:
                logger.debug(f"Cache hit for artwork: {artist} - {title}")
            else:
                logger.debug(f"Cache hit (known no artwork): {artist} - {title}")
            return cached_url

        # 2. Try primary fallback: Deezer API (Discord-compatible CDN URLs)
        try:
            url = await self._deezer.get_artwork_url(artist, title, album)
            if url:
                self._cache.set(artist, title, url)
                return url
        except Exception as e:
            logger.warning(f"Deezer artwork lookup failed for {artist} - {title}: {e}")

        # 3. Try secondary fallback: MusicBrainz + Cover Art Archive
        try:
            url = await self._musicbrainz.get_artwork_url(artist, title, album)
            if url:
                self._cache.set(artist, title, url)
                return url
        except Exception as e:
            logger.warning(f"MusicBrainz artwork lookup failed for {artist} - {title}: {e}")

        # 4. No artwork found across providers -> cache negative result
        self._cache.set(artist, title, None)
        return None

    async def close(self) -> None:
        try:
            await self._deezer.close()
        except Exception as e:
            logger.warning(f"Error closing Deezer provider: {e}")

        try:
            await self._musicbrainz.close()
        except Exception as e:
            logger.warning(f"Error closing MusicBrainz provider: {e}")
