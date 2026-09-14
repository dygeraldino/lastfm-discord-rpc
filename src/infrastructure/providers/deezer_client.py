import asyncio
import httpx
from typing import Optional

from src.domain.interfaces.artwork_provider import ArtworkProvider
from config.logging_config import get_logger

logger = get_logger(__name__)

USER_AGENT = "LastfmPresence/1.0.0 ( https://github.com/dygeraldino/lastfm-discord-rpc )"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
RATE_LIMIT_SECONDS = 0.5


class DeezerArtworkProvider(ArtworkProvider):
    """Fetches album art from Deezer's public API (no API key required).

    Deezer CDN URLs (cdn-images.dzcdn.net) are hotlink-friendly and work
    correctly as Discord Rich Presence large_image external URLs.
    """

    def __init__(self) -> None:
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

        await self._rate_limit()
        client = await self._get_client()

        # Search by track: "{artist} {title}"
        query = f"{artist} {title}".strip()
        url = await self._search_deezer(client, query)
        if url:
            logger.info(f"Found Deezer artwork for song: {artist} - {title}")
            return url

        # Fallback: search by album if different from title
        if album and album.strip() and album.strip().lower() != title.strip().lower():
            query_album = f"{artist} {album}".strip()
            url = await self._search_deezer(client, query_album)
            if url:
                logger.info(f"Found Deezer artwork for album: {artist} - {album}")
                return url

        return None

    async def _search_deezer(self, client: httpx.AsyncClient, query: str) -> Optional[str]:
        params = {
            "q": query,
            "limit": 3,
        }

        try:
            response = await client.get(DEEZER_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("data", [])
            for result in results:
                album = result.get("album", {})
                # Prefer xl > big > medium cover sizes
                cover = (
                    album.get("cover_xl")
                    or album.get("cover_big")
                    or album.get("cover_medium")
                    or album.get("cover")
                )
                if cover and "dzcdn.net" in cover:
                    return cover

            return None

        except httpx.HTTPStatusError as e:
            logger.warning(f"Deezer search HTTP error [{e.response.status_code}] for '{query}'")
            return None
        except httpx.RequestError as e:
            logger.warning(f"Deezer search network error for '{query}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Deezer search unexpected error for '{query}': {e}")
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("Deezer HTTP client closed")
