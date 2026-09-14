import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.infrastructure.providers.deezer_client import DeezerArtworkProvider


class TestDeezerArtworkProvider:
    @pytest.fixture
    def provider(self):
        return DeezerArtworkProvider()

    @pytest.mark.asyncio
    async def test_empty_artist_returns_none(self, provider):
        result = await provider.get_artwork_url("", "Song")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_title_returns_none(self, provider):
        result = await provider.get_artwork_url("Artist", "")
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_track_search(self, provider):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {
                    "album": {
                        "cover_xl": "https://e-cdns-images.dzcdn.net/images/cover/123/1000x1000-000000-80-0-0.jpg"
                    }
                }
            ]
        }

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)
            with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
                url = await provider.get_artwork_url("Daft Punk", "Get Lucky")
                assert url == "https://e-cdns-images.dzcdn.net/images/cover/123/1000x1000-000000-80-0-0.jpg"

    @pytest.mark.asyncio
    async def test_fallback_to_album_search(self, provider):
        mock_empty_response = MagicMock()
        mock_empty_response.raise_for_status.return_value = None
        mock_empty_response.json.return_value = {"data": []}

        mock_album_response = MagicMock()
        mock_album_response.raise_for_status.return_value = None
        mock_album_response.json.return_value = {
            "data": [
                {
                    "album": {
                        "cover_big": "https://e-cdns-images.dzcdn.net/images/cover/456/500x500-000000-80-0-0.jpg"
                    }
                }
            ]
        }

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.get = AsyncMock(side_effect=[mock_empty_response, mock_album_response])
            with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
                url = await provider.get_artwork_url("Daft Punk", "Get Lucky", album="Random Access Memories")
                assert url == "https://e-cdns-images.dzcdn.net/images/cover/456/500x500-000000-80-0-0.jpg"

    @pytest.mark.asyncio
    async def test_no_dzcdn_link_ignored(self, provider):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "data": [
                {
                    "album": {
                        "cover_xl": "https://invalid-host.com/cover.jpg"
                    }
                }
            ]
        }

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.get = AsyncMock(return_value=mock_response)
            with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
                url = await provider.get_artwork_url("Unknown", "Track")
                assert url is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, provider):
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.get = AsyncMock(side_effect=Exception("Network failure"))
            with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
                url = await provider.get_artwork_url("Artist", "Track")
                assert url is None

    @pytest.mark.asyncio
    async def test_close(self, provider):
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client

        await provider.close()
        mock_client.aclose.assert_called_once()
