import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.infrastructure.providers.musicbrainz_client import MusicBrainzArtworkProvider
from src.infrastructure.persistence.json_artwork_cache_repository import JsonArtworkCacheRepository


@pytest.fixture
def temp_cache_dir(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "artwork_cache.json"
    return cache_file


@pytest.fixture
def cache_repo(temp_cache_dir):
    repo = JsonArtworkCacheRepository()
    repo._cache_file = temp_cache_dir
    repo._cache_dir = temp_cache_dir.parent
    repo._loaded = False
    return repo


class TestJsonArtworkCacheRepository:
    def test_make_key_slugifies_correctly(self, cache_repo):
        key = cache_repo._make_key("The Beatles", "Abbey Road")
        assert key == "the_beatles:abbey_road"

    def test_make_key_handles_special_chars(self, cache_repo):
        key = cache_repo._make_key("Artist & Band", "Album (Deluxe)")
        assert key == "artist_band:album_deluxe"

    def test_get_set_roundtrip(self, cache_repo):
        cache_repo.set("Artist", "Album", "https://example.com/cover.jpg")
        assert cache_repo.get("Artist", "Album") == "https://example.com/cover.jpg"

    def test_set_none_caches_miss(self, cache_repo):
        cache_repo.set("Artist", "Album", None)
        assert cache_repo.get("Artist", "Album") is None

    def test_get_missing_returns_none(self, cache_repo):
        assert cache_repo.get("Unknown", "Album") is None

    def test_persists_to_disk(self, cache_repo):
        cache_repo.set("Artist", "Album", "https://example.com/cover.jpg")
        cache_repo._loaded = False
        assert cache_repo.get("Artist", "Album") == "https://example.com/cover.jpg"


class TestMusicBrainzArtworkProvider:
    @pytest.fixture
    def provider(self, cache_repo):
        return MusicBrainzArtworkProvider(cache=cache_repo)

    @pytest.mark.asyncio
    async def test_get_artwork_url_empty_artist_returns_none(self, provider):
        result = await provider.get_artwork_url("", "Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_artwork_url_empty_title_returns_none(self, provider):
        result = await provider.get_artwork_url("Artist", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_url(self, provider, cache_repo):
        cache_repo.set("Artist", "Title", "https://cached.com/art.jpg")
        result = await provider.get_artwork_url("Artist", "Title")
        assert result == "https://cached.com/art.jpg"

    @pytest.mark.asyncio
    async def test_returns_none_for_cached_miss(self, provider, cache_repo):
        cache_repo.set("Artist", "Title", None)
        result = await provider.get_artwork_url("Artist", "Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_musicbrainz_returns_mbid(self, provider):
        with patch.object(provider, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "releases": [{"id": "test-mbid-123"}]
            }
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            mbid = await provider._search_musicbrainz("Artist", "Title")
            assert mbid == "test-mbid-123"

    @pytest.mark.asyncio
    async def test_search_musicbrainz_no_results_returns_none(self, provider):
        with patch.object(provider, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"releases": []}
            mock_response.raise_for_status.return_value = None
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            mbid = await provider._search_musicbrainz("Artist", "Title")
            assert mbid is None

    @pytest.mark.asyncio
    async def test_check_cover_art_success(self, provider):
        with patch.object(provider, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.head = AsyncMock(return_value=mock_response)

            url = await provider._check_cover_art("test-mbid")
            assert url == "https://coverartarchive.org/release/test-mbid/front-500"

    @pytest.mark.asyncio
    async def test_check_cover_art_not_found(self, provider):
        with patch.object(provider, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.return_value.head = AsyncMock(return_value=mock_response)

            url = await provider._check_cover_art("test-mbid")
            assert url is None

    @pytest.mark.asyncio
    async def test_full_flow_success(self, provider):
        with patch.object(provider, "_search_musicbrainz", return_value="mbid-123") as mock_search:
            with patch.object(provider, "_check_cover_art", return_value="https://coverartarchive.org/release/mbid-123/front-500") as mock_check:
                result = await provider.get_artwork_url("Artist", "Title", "Album")
                assert result == "https://coverartarchive.org/release/mbid-123/front-500"
                mock_search.assert_called_once_with("Artist", "Album")
                mock_check.assert_called_once_with("mbid-123")

    @pytest.mark.asyncio
    async def test_full_flow_no_mbid(self, provider):
        with patch.object(provider, "_search_musicbrainz", return_value=None):
            result = await provider.get_artwork_url("Artist", "Title")
            assert result is None

    @pytest.mark.asyncio
    async def test_full_flow_no_cover_art(self, provider):
        with patch.object(provider, "_search_musicbrainz", return_value="mbid-123"):
            with patch.object(provider, "_check_cover_art", return_value=None):
                result = await provider.get_artwork_url("Artist", "Title")
                assert result is None

    @pytest.mark.asyncio
    async def test_close_closes_client(self, provider):
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client

        await provider.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self, provider):
        start = asyncio.get_event_loop().time()
        await provider._rate_limit()
        await provider._rate_limit()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 1.0