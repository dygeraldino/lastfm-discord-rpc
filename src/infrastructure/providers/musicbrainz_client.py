import asyncio
from typing import Optional
import httpx

from src.domain.interfaces.artwork_provider import ArtworkProvider
from src.infrastructure.persistence.json_artwork_cache_repository import JsonArtworkCacheRepository
from config.logging_config import get_logger

logger = get_logger(__name__)

USER_AGENT = "LastfmPresence/1.0.0 ( https://github.com/dygeraldino/lastfm-discord-rpc )"
MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/release/"
COVERART_ARCHIVE_BASE_URL = "https://coverartarchive.org/release/"
RATE_LIMIT_SECONDS = 1.0


class MusicBrainzArtworkProvider(ArtworkProvider):
    """Fetches album artwork from MusicBrainz + Cover Art Archive.

    Flow:
      1. Check persistent JSON cache (if cache repo provided).
      2. Search MusicBrainz API for release MBID.
      3. Check Cover Art Archive (HEAD request for front-500).
      4. Rate limit: 1 request/sec to comply with MusicBrainz policy.
    """

    def __init__(self, cache: JsonArtworkCacheRepository | None = None) -> None:
        self._cache = cache
        self._client: httpx.AsyncClient | None = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=4.0),
                headers={"User-Agent": USER_AGENT},
                limits=httpx.Limits(max_connections=3, max_keepalive_connections=1),
            )
        return self._client

    async def _rate_limit(self) -> None:
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_SECONDS:
                await asyncio.sleep(RATE_LIMIT_SECONDS - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def get_artwork_url(self, artist: str, title: str, album: str = "") -> Optional[str]:
        if not artist or not title:
            return None

        # 1. Check cache if repository attached
        if self._cache:
            is_cached, cached_url = self._cache.get_entry(artist, title)
            if is_cached:
                return cached_url

        # Search terms: prefer album if available, otherwise track/album title
        release_title = album.strip() if album and album.strip() else title.strip()

        # 2. Search MusicBrainz for MBID
        mbid = await self._search_musicbrainz(artist, release_title)
        if not mbid:
            if self._cache:
                self._cache.set(artist, title, None)
            return None

        # 3. Check Cover Art Archive
        artwork_url = await self._check_cover_art(mbid)

        if self._cache:
            self._cache.set(artist, title, artwork_url)

        return artwork_url

    async def _search_musicbrainz(self, artist: str, release_title: str) -> Optional[str]:
        await self._rate_limit()
        client = await self._get_client()

        query = f'artist:"{artist}" AND release:"{release_title}"'
        params = {"query": query, "fmt": "json", "limit": 1}

        try:
            response = await client.get(MUSICBRAINZ_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            releases = data.get("releases", [])
            if releases:
                return releases[0].get("id")
            return None

        except httpx.HTTPStatusError as e:
            logger.warning(f"MusicBrainz search HTTP error [{e.response.status_code}] for '{query}'")
            return None
        except httpx.RequestError as e:
            logger.warning(f"MusicBrainz search network error for '{query}': {e}")
            return None
        except Exception as e:
            logger.warning(f"MusicBrainz search unexpected error for '{query}': {e}")
            return None

    async def _check_cover_art(self, mbid: str) -> Optional[str]:
        client = await self._get_client()
        url = f"{COVERART_ARCHIVE_BASE_URL}{mbid}/front-500"

        try:
            response = await client.head(url, follow_redirects=True)
            if response.status_code == 200:
                return url
            return None
        except Exception as e:
            logger.warning(f"Cover Art Archive check failed for MBID {mbid}: {e}")
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("MusicBrainz HTTP client closed")
