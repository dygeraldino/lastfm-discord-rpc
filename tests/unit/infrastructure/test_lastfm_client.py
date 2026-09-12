import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.domain.entities.track import Track
from src.domain.exceptions import ProviderError
from datetime import datetime


class TestLastFmClient:
    @pytest.fixture
    def client(self):
        return LastFmClient()

    @pytest.mark.asyncio
    async def test_get_current_track_returns_none_on_empty_response(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"recenttracks": {"track": []}}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            result = await client.get_current_track()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_track_returns_none_when_not_playing(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recenttracks": {
                "track": [{
                    "name": "Song",
                    "artist": {"#text": "Artist"},
                    "album": {"#text": "Album"},
                    "image": [],
                    "@attr": {"nowplaying": "false"},
                }]
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            result = await client.get_current_track()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_track_parses_artist_name_key(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recenttracks": {
                "track": [{
                    "name": "Mimos",
                    "artist": {"name": "Test Artist Name"},
                    "album": {"name": "Test Album Name"},
                    "image": [],
                    "@attr": {"nowplaying": "true"},
                }]
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            result = await client.get_current_track()

        assert result is not None
        assert result.title == "Mimos"
        assert result.artist == "Test Artist Name"
        assert result.album == "Test Album Name"
        assert result.is_playing is True

    @pytest.mark.asyncio
    async def test_get_current_track_returns_track_when_playing(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recenttracks": {
                "track": [{
                    "name": "Test Song",
                    "artist": {"#text": "Test Artist"},
                    "album": {"#text": "Test Album"},
                    "image": [
                        {"size": "small", "#text": "small.jpg"},
                        {"size": "large", "#text": "large.jpg"},
                        {"size": "extralarge", "#text": "extralarge.jpg"},
                    ],
                    "@attr": {"nowplaying": "true"},
                    "date": {"uts": "1704115200"},
                }]
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            result = await client.get_current_track()

        assert result is not None
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.artwork_url == "extralarge.jpg"
        assert result.is_playing is True
        assert result.timestamp == datetime.fromtimestamp(1704115200)

    @pytest.mark.asyncio
    async def test_get_current_track_uses_largest_available_image(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recenttracks": {
                "track": [{
                    "name": "Song",
                    "artist": {"#text": "Artist"},
                    "album": {"#text": "Album"},
                    "image": [
                        {"size": "small", "#text": "small.jpg"},
                        {"size": "medium", "#text": "medium.jpg"},
                    ],
                    "@attr": {"nowplaying": "true"},
                }]
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            result = await client.get_current_track()

        assert result.artwork_url == "medium.jpg"

    @pytest.mark.asyncio
    async def test_get_current_track_raises_on_api_error(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": 6, "message": "Invalid API key"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_get_client.return_value = mock_http

            with pytest.raises(ProviderError) as exc_info:
                await client.get_current_track()

            assert "Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self, client):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        client._client = mock_http

        await client.close()

        mock_http.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_does_nothing_if_client_none(self, client):
        client._client = None
        await client.close()