import httpx
from typing import Optional
from urllib.parse import quote
from src.domain.interfaces.music_provider import MusicProvider
from src.domain.entities.track import Track
from src.domain.exceptions import ProviderError
from config.settings import settings
from config.logging_config import get_logger
from datetime import datetime


logger = get_logger(__name__)


class LastFmClient(MusicProvider):
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._base_url = settings.lastfm_base_url
        self._api_key = settings.lastfm_api_key
        self._username = settings.lastfm_username

    def _build_lastfm_urls(self, artist: str, title: str) -> list[tuple[str, str]]:
        """Build Last.fm URLs for track and artist with proper URL encoding."""
        encoded_artist = quote(artist, safe="")
        encoded_title = quote(title, safe="")
        track_url = f"https://www.last.fm/music/{encoded_artist}/_/{encoded_title}"
        artist_url = f"https://www.last.fm/music/{encoded_artist}"
        return [
            ("Listen on Last.fm", track_url),
            ("View Artist", artist_url),
        ]

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def get_current_track(self) -> Optional[Track]:
        client = await self._get_client()
        params = {
            "method": "user.getRecentTracks",
            "user": self._username,
            "api_key": self._api_key,
            "format": "json",
            "limit": 1,
            "extended": 1,
        }

        try:
            response = await self._make_request_with_retry(client, params)
            data = response.json()
            return self._parse_track(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after_hdr = e.response.headers.get("Retry-After")
                retry_after = int(float(retry_after_hdr)) if retry_after_hdr else 60
                logger.warning(f"Rate limited by Last.fm, waiting {retry_after}s")
                raise ProviderError(f"Rate limited, retry after {retry_after}s") from e
            logger.error(f"HTTP error from Last.fm: {e.response.status_code}")
            raise ProviderError(f"HTTP error: {e.response.status_code}") from e
        except ProviderError:
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error calling Last.fm: {e}")
            raise ProviderError(f"Network error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error parsing Last.fm response: {e}")
            raise ProviderError(f"Parse error: {e}") from e

    async def _make_request_with_retry(
        self, client: httpx.AsyncClient, params: dict
    ) -> httpx.Response:
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await client.get(self._base_url, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after_hdr = e.response.headers.get("Retry-After")
                    retry_after = int(float(retry_after_hdr)) if retry_after_hdr else int(base_delay * (2**attempt))
                    import asyncio
                    await asyncio.sleep(retry_after)
                    continue
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(base_delay * (2**attempt))
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(base_delay * (2**attempt))
                    continue
                raise

        raise ProviderError("Max retries exceeded")

    def _parse_track(self, data: dict) -> Optional[Track]:
        if "error" in data:
            err_code = data.get("error")
            err_msg = data.get("message", "Unknown Last.fm error")
            logger.error(f"Last.fm API error [{err_code}]: {err_msg}")
            raise ProviderError(f"Last.fm API error [{err_code}]: {err_msg}")

        try:
            recent_tracks = data.get("recenttracks", {})
            tracks = recent_tracks.get("track", [])

            if not tracks:
                return None

            track_data = tracks[0] if isinstance(tracks, list) else tracks

            now_playing = track_data.get("@attr", {}).get("nowplaying") == "true"

            if not now_playing:
                return None

            title = track_data.get("name", "")
            raw_artist = track_data.get("artist", "")
            if isinstance(raw_artist, dict):
                artist = raw_artist.get("#text") or raw_artist.get("name", "")
            else:
                artist = str(raw_artist)

            raw_album = track_data.get("album", "")
            if isinstance(raw_album, dict):
                album = raw_album.get("#text") or raw_album.get("name", "")
            else:
                album = str(raw_album)

            artwork_url = ""
            images = track_data.get("image", [])
            for size in ("extralarge", "large", "medium", "small"):
                for img in images:
                    if img.get("size") == size:
                        artwork_url = img.get("#text", "")
                        break
                if artwork_url:
                    break

            timestamp_str = track_data.get("date", {}).get("uts") if isinstance(track_data.get("date"), dict) else None
            timestamp = datetime.fromtimestamp(int(timestamp_str)) if timestamp_str else datetime.now()

            button_urls = self._build_lastfm_urls(artist, title)

            return Track(
                title=title,
                artist=artist,
                album=album,
                artwork_url=artwork_url,
                is_playing=True,
                timestamp=timestamp,
                button_urls=button_urls,
            )
        except Exception as e:
            logger.error(f"Error parsing track data: {e}")
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("Last.fm HTTP client closed")