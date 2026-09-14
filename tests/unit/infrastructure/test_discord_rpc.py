import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.infrastructure.publishers.discord_rpc import DiscordRpcPublisher
from src.domain.entities.track import Track
from src.domain.exceptions import PublisherError
from pypresence.exceptions import DiscordNotFound, PipeClosed, InvalidID
from datetime import datetime


class TestDiscordRpcPublisher:
    @pytest.fixture
    def publisher(self):
        p = DiscordRpcPublisher()
        p._client_id = "test_client_id"
        return p

    @pytest.fixture
    def sample_track(self):
        return Track(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            artwork_url="https://example.com/art.jpg",
            is_playing=True,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

    @pytest.fixture
    def sample_track_with_buttons(self):
        return Track(
            title="Come Together",
            artist="The Beatles",
            album="Abbey Road",
            artwork_url="https://example.com/art.jpg",
            is_playing=True,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            button_urls=[
                ("Listen on Last.fm", "https://www.last.fm/music/The%20Beatles/_/Come%20Together"),
                ("View Artist", "https://www.last.fm/music/The%20Beatles"),
            ],
        )

    @pytest.mark.asyncio
    async def test_connect_success(self, publisher):
        with patch("src.infrastructure.publishers.discord_rpc.Presence") as mock_presence_class:
            mock_client = MagicMock()
            mock_presence_class.return_value = mock_client

            await publisher.connect()

            mock_presence_class.assert_called_once_with(publisher._client_id)
            mock_client.connect.assert_called_once()
            assert publisher._connected is True

    @pytest.mark.asyncio
    async def test_connect_discord_not_found(self, publisher):
        with patch("src.infrastructure.publishers.discord_rpc.Presence") as mock_presence_class:
            mock_client = MagicMock()
            mock_client.connect.side_effect = DiscordNotFound()
            mock_presence_class.return_value = mock_client

            await publisher.connect()

            assert publisher._connected is False

    @pytest.mark.asyncio
    async def test_connect_invalid_id_raises(self, publisher):
        with patch("src.infrastructure.publishers.discord_rpc.Presence") as mock_presence_class:
            mock_client = MagicMock()
            mock_client.connect.side_effect = InvalidID()
            mock_presence_class.return_value = mock_client

            with pytest.raises(PublisherError) as exc_info:
                await publisher.connect()

            assert "Invalid Discord Client ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_closes_client(self, publisher):
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        await publisher.disconnect()

        mock_client.close.assert_called_once()
        assert publisher._connected is False
        assert publisher._client is None

    @pytest.mark.asyncio
    async def test_update_sends_correct_data(self, publisher, sample_track):
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        await publisher.update(sample_track)

        mock_client.update.assert_called_once()
        call_kwargs = mock_client.update.call_args.kwargs
        assert call_kwargs["details"] == "Test Song"
        assert call_kwargs["state"] == "by Test Artist"
        assert call_kwargs["large_image"] == "https://example.com/art.jpg"
        assert call_kwargs["large_text"] == "Test Album"
        assert call_kwargs["small_image"] == "lastfm"
        assert call_kwargs["small_text"] == "Last.fm"
        assert call_kwargs["start"] == int(datetime(2024, 1, 1, 12, 0, 0).timestamp())

    @pytest.mark.asyncio
    async def test_update_reconnects_on_pipe_closed(self, publisher, sample_track):
        mock_client = MagicMock()
        # Raise PipeClosed on first call, succeed on second
        mock_client.update.side_effect = [PipeClosed(), None]
        publisher._client = mock_client
        publisher._connected = True

        with patch.object(publisher, "_try_reconnect", new_callable=AsyncMock) as mock_reconnect:
            mock_reconnect.side_effect = lambda: setattr(publisher, "_connected", True)

            await publisher.update(sample_track)

            mock_reconnect.assert_awaited_once()
            assert mock_client.update.call_count == 2

    @pytest.mark.asyncio
    async def test_update_raises_on_reconnect_failure(self, publisher, sample_track):
        mock_client = MagicMock()
        mock_client.update.side_effect = PipeClosed()
        publisher._client = mock_client
        publisher._connected = True

        with patch.object(publisher, "_try_reconnect", new_callable=AsyncMock) as mock_reconnect:
            mock_reconnect.side_effect = lambda: None

            with pytest.raises(PublisherError) as exc_info:
                await publisher.update(sample_track)

            assert "Discord reconnection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_clear_calls_client_clear(self, publisher):
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        await publisher.clear()

        mock_client.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_handles_disconnect_gracefully(self, publisher):
        mock_client = MagicMock()
        mock_client.clear.side_effect = PipeClosed()
        publisher._client = mock_client
        publisher._connected = True

        await publisher.clear()

        assert publisher._connected is False

    @pytest.mark.asyncio
    async def test_update_sends_buttons_when_enabled(self, publisher, sample_track_with_buttons):
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        with patch("src.infrastructure.publishers.discord_rpc.settings") as mock_settings:
            mock_settings.enable_rich_presence_buttons = True

            await publisher.update(sample_track_with_buttons)

        mock_client.update.assert_called_once()
        call_kwargs = mock_client.update.call_args.kwargs
        assert "buttons" in call_kwargs
        assert len(call_kwargs["buttons"]) == 2
        assert call_kwargs["buttons"][0]["label"] == "Listen on Last.fm"
        assert call_kwargs["buttons"][0]["url"] == "https://www.last.fm/music/The%20Beatles/_/Come%20Together"
        assert call_kwargs["buttons"][1]["label"] == "View Artist"
        assert call_kwargs["buttons"][1]["url"] == "https://www.last.fm/music/The%20Beatles"

    @pytest.mark.asyncio
    async def test_update_does_not_send_buttons_when_disabled(self, publisher, sample_track_with_buttons):
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        with patch("src.infrastructure.publishers.discord_rpc.settings") as mock_settings:
            mock_settings.enable_rich_presence_buttons = False

            await publisher.update(sample_track_with_buttons)

        mock_client.update.assert_called_once()
        call_kwargs = mock_client.update.call_args.kwargs
        assert "buttons" not in call_kwargs

    @pytest.mark.asyncio
    async def test_update_sends_buttons_without_artwork(self, publisher):
        track = Track(
            title="Song",
            artist="Artist",
            is_playing=True,
            button_urls=[("Listen", "https://example.com")],
        )
        mock_client = MagicMock()
        publisher._client = mock_client
        publisher._connected = True

        with patch("src.infrastructure.publishers.discord_rpc.settings") as mock_settings:
            mock_settings.enable_rich_presence_buttons = True

            await publisher.update(track)

        call_kwargs = mock_client.update.call_args.kwargs
        assert "buttons" in call_kwargs
        assert len(call_kwargs["buttons"]) == 1