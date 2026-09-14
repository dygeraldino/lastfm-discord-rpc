from unittest.mock import AsyncMock, MagicMock
import pytest

from src.infrastructure.providers.fallback_artwork_provider import FallbackArtworkProvider
from src.infrastructure.persistence.json_artwork_cache_repository import JsonArtworkCacheRepository


class TestFallbackArtworkProvider:
    @pytest.fixture
    def cache_repo(self, tmp_path):
        repo = JsonArtworkCacheRepository()
        repo._cache_file = tmp_path / "cache.json"
        repo._cache_dir = tmp_path
        repo._loaded = False
        return repo

    @pytest.fixture
    def mock_deezer(self):
        provider = MagicMock()
        provider.get_artwork_url = AsyncMock(return_value=None)
        provider.close = AsyncMock()
        return provider

    @pytest.fixture
    def mock_mb(self):
        provider = MagicMock()
        provider.get_artwork_url = AsyncMock(return_value=None)
        provider.close = AsyncMock()
        return provider

    @pytest.fixture
    def fallback_provider(self, cache_repo, mock_deezer, mock_mb):
        return FallbackArtworkProvider(
            cache=cache_repo,
            deezer_provider=mock_deezer,
            musicbrainz_provider=mock_mb,
        )

    @pytest.mark.asyncio
    async def test_returns_cached_url(self, fallback_provider, cache_repo, mock_deezer):
        cache_repo.set("Artist", "Title", "https://cached.com/img.jpg")

        url = await fallback_provider.get_artwork_url("Artist", "Title")
        assert url == "https://cached.com/img.jpg"
        mock_deezer.get_artwork_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_cached_negative_lookup(self, fallback_provider, cache_repo, mock_deezer, mock_mb):
        cache_repo.set("Artist", "Title", None)

        url = await fallback_provider.get_artwork_url("Artist", "Title")
        assert url is None
        mock_deezer.get_artwork_url.assert_not_called()
        mock_mb.get_artwork_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_deezer_primary_hit(self, fallback_provider, cache_repo, mock_deezer, mock_mb):
        mock_deezer.get_artwork_url.return_value = "https://e-cdns-images.dzcdn.net/art.jpg"

        url = await fallback_provider.get_artwork_url("Artist", "Title")
        assert url == "https://e-cdns-images.dzcdn.net/art.jpg"
        mock_deezer.get_artwork_url.assert_called_once_with("Artist", "Title", "")
        mock_mb.get_artwork_url.assert_not_called()
        assert cache_repo.get("Artist", "Title") == "https://e-cdns-images.dzcdn.net/art.jpg"

    @pytest.mark.asyncio
    async def test_musicbrainz_secondary_hit(self, fallback_provider, cache_repo, mock_deezer, mock_mb):
        mock_deezer.get_artwork_url.return_value = None
        mock_mb.get_artwork_url.return_value = "https://coverartarchive.org/art.jpg"

        url = await fallback_provider.get_artwork_url("Artist", "Title")
        assert url == "https://coverartarchive.org/art.jpg"
        mock_deezer.get_artwork_url.assert_called_once()
        mock_mb.get_artwork_url.assert_called_once()
        assert cache_repo.get("Artist", "Title") == "https://coverartarchive.org/art.jpg"

    @pytest.mark.asyncio
    async def test_both_miss_caches_none(self, fallback_provider, cache_repo, mock_deezer, mock_mb):
        mock_deezer.get_artwork_url.return_value = None
        mock_mb.get_artwork_url.return_value = None

        url = await fallback_provider.get_artwork_url("Artist", "Title")
        assert url is None
        is_cached, value = cache_repo.get_entry("Artist", "Title")
        assert is_cached is True
        assert value is None

    @pytest.mark.asyncio
    async def test_close_calls_all(self, fallback_provider, mock_deezer, mock_mb):
        await fallback_provider.close()
        mock_deezer.close.assert_called_once()
        mock_mb.close.assert_called_once()
