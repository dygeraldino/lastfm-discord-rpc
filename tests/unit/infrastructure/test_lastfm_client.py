import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.domain.interfaces.artwork_provider import ArtworkProvider
from src.domain.entities.track import Track
from src.domain.exceptions import ProviderError
from datetime import datetime
from config.settings import settings as settings_obj


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

    def test_build_lastfm_urls_encodes_special_characters(self, client):
        buttons = client._build_lastfm_urls("AC/DC", "Highway to Hell")
        assert len(buttons) == 2
        assert buttons[0][0] == "Listen on Last.fm"
        assert "AC%2FDC" in buttons[0][1]
        assert "Highway%20to%20Hell" in buttons[0][1]
        assert buttons[1][0] == "View Artist"
        assert "AC%2FDC" in buttons[1][1]

    def test_build_lastfm_urls_unicode_characters(self, client):
        buttons = client._build_lastfm_urls("Björk", "Jóga")
        assert "Bj%C3%B6rk" in buttons[0][1]
        assert "J%C3%B3ga" in buttons[0][1]

    @pytest.mark.asyncio
    async def test_get_current_track_includes_button_urls(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "recenttracks": {
                "track": [{
                    "name": "Come Together",
                    "artist": {"#text": "The Beatles"},
                    "album": {"#text": "Abbey Road"},
                    "image": [{"size": "extralarge", "#text": "cover.jpg"}],
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
        assert len(result.button_urls) == 2
        assert result.button_urls[0][0] == "Listen on Last.fm"
        assert "The%20Beatles" in result.button_urls[0][1]
        assert "Come%20Together" in result.button_urls[0][1]
        assert result.button_urls[1][0] == "View Artist"
        assert "The%20Beatles" in result.button_urls[1][1]


class TestLastFmClientFallbackArtwork:
    @pytest.fixture
    def mock_artwork_provider(self):
        provider = MagicMock(spec=ArtworkProvider)
        provider.get_artwork_url = AsyncMock(return_value="https://fallback.com/art.jpg")
        provider.close = AsyncMock()
        return provider

    @pytest.fixture
    def client_with_fallback(self, mock_artwork_provider):
        return LastFmClient(artwork_provider=mock_artwork_provider)

    @pytest.mark.asyncio
    async def test_uses_fallback_when_no_artwork_and_enabled(self, client_with_fallback, mock_artwork_provider):
        original_enabled = settings_obj.enable_fallback_artwork
        settings_obj.enable_fallback_artwork = True
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "recenttracks": {
                    "track": [{
                        "name": "Song",
                        "artist": {"#text": "Artist"},
                        "album": {"#text": "Album"},
                        "image": [],
                        "@attr": {"nowplaying": "true"},
                    }]
                }
            }

            with patch.object(client_with_fallback, "_get_client") as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = mock_response
                mock_get_client.return_value = mock_http

                result = await client_with_fallback.get_current_track()

            assert result is not None
            assert result.artwork_url == "https://fallback.com/art.jpg"
            mock_artwork_provider.get_artwork_url.assert_awaited_once_with("Artist", "Song", "Album")
        finally:
            settings_obj.enable_fallback_artwork = original_enabled

    @pytest.mark.asyncio
    async def test_does_not_use_fallback_when_disabled(self, client_with_fallback, mock_artwork_provider):
        original_enabled = settings_obj.enable_fallback_artwork
        settings_obj.enable_fallback_artwork = False
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "recenttracks": {
                    "track": [{
                        "name": "Song",
                        "artist": {"#text": "Artist"},
                        "album": {"#text": "Album"},
                        "image": [],
                        "@attr": {"nowplaying": "true"},
                    }]
                }
            }

            with patch.object(client_with_fallback, "_get_client") as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = mock_response
                mock_get_client.return_value = mock_http

                result = await client_with_fallback.get_current_track()

            assert result is not None
            assert result.artwork_url == ""
            mock_artwork_provider.get_artwork_url.assert_not_awaited()
        finally:
            settings_obj.enable_fallback_artwork = original_enabled

    @pytest.mark.asyncio
    async def test_uses_lastfm_artwork_when_available(self, client_with_fallback, mock_artwork_provider):
        original_enabled = settings_obj.enable_fallback_artwork
        settings_obj.enable_fallback_artwork = True
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "recenttracks": {
                    "track": [{
                        "name": "Song",
                        "artist": {"#text": "Artist"},
                        "album": {"#text": "Album"},
                        "image": [{"size": "extralarge", "#text": "lastfm_cover.jpg"}],
                        "@attr": {"nowplaying": "true"},
                    }]
                }
            }

            with patch.object(client_with_fallback, "_get_client") as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = mock_response
                mock_get_client.return_value = mock_http

                result = await client_with_fallback.get_current_track()

            assert result is not None
            assert result.artwork_url == "lastfm_cover.jpg"
            mock_artwork_provider.get_artwork_url.assert_not_awaited()
        finally:
            settings_obj.enable_fallback_artwork = original_enabled

    @pytest.mark.asyncio
    async def test_fallback_provider_error_handled_gracefully(self, client_with_fallback, mock_artwork_provider):
        original_enabled = settings_obj.enable_fallback_artwork
        settings_obj.enable_fallback_artwork = True
        mock_artwork_provider.get_artwork_url.side_effect = Exception("Network error")
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "recenttracks": {
                    "track": [{
                        "name": "Song",
                        "artist": {"#text": "Artist"},
                        "album": {"#text": "Album"},
                        "image": [],
                        "@attr": {"nowplaying": "true"},
                    }]
                }
            }

            with patch.object(client_with_fallback, "_get_client") as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = mock_response
                mock_get_client.return_value = mock_http

                result = await client_with_fallback.get_current_track()

            assert result is not None
            assert result.artwork_url == ""
        finally:
            settings_obj.enable_fallback_artwork = original_enabled

    @pytest.mark.asyncio
    async def test_uses_fallback_when_lastfm_returns_placeholder_png(self, client_with_fallback, mock_artwork_provider):
        original_enabled = settings_obj.enable_fallback_artwork
        settings_obj.enable_fallback_artwork = True
        try:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "recenttracks": {
                    "track": [{
                        "name": "Song",
                        "artist": {"#text": "Artist"},
                        "album": {"#text": "Album"},
                        "image": [{"size": "extralarge", "#text": "https://lastfm-img.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png"}],
                        "@attr": {"nowplaying": "true"},
                    }]
                }
            }

            with patch.object(client_with_fallback, "_get_client") as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = mock_response
                mock_get_client.return_value = mock_http

                result = await client_with_fallback.get_current_track()

            assert result is not None
            assert result.artwork_url == "https://fallback.com/art.jpg"
            mock_artwork_provider.get_artwork_url.assert_awaited_once_with("Artist", "Song", "Album")
        finally:
            settings_obj.enable_fallback_artwork = original_enabled

    @pytest.mark.asyncio
    async def test_close_calls_artwork_provider_close(self, client_with_fallback, mock_artwork_provider):
        await client_with_fallback.close()
        mock_artwork_provider.close.assert_awaited_once()