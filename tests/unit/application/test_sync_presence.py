import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.use_cases.sync_presence import SyncPresenceUseCase
from src.domain.entities.track import Track
from src.domain.interfaces.music_provider import MusicProvider
from src.domain.interfaces.presence_publisher import PresencePublisher
from src.domain.exceptions import ProviderError, PublisherError


class TestSyncPresenceUseCase:
    @pytest.fixture
    def mock_provider(self):
        return AsyncMock(spec=MusicProvider)

    @pytest.fixture
    def mock_publisher(self):
        return AsyncMock(spec=PresencePublisher)

    @pytest.fixture
    def use_case(self, mock_provider, mock_publisher):
        return SyncPresenceUseCase(mock_provider, mock_publisher)

    @pytest.fixture
    def sample_track(self):
        return Track(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            artwork_url="https://example.com/art.jpg",
            is_playing=True,
        )

    @pytest.mark.asyncio
    async def test_execute_updates_presence_on_new_track(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track

        await use_case.execute()

        mock_provider.get_current_track.assert_awaited_once()
        mock_publisher.update.assert_awaited_once_with(sample_track)
        assert use_case._last_track_hash == sample_track.hash_key

    @pytest.mark.asyncio
    async def test_execute_skips_when_track_unchanged(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track

        await use_case.execute()
        await use_case.execute()

        assert mock_provider.get_current_track.await_count == 2
        assert mock_publisher.update.await_count == 1

    @pytest.mark.asyncio
    async def test_execute_clears_when_not_playing(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track
        await use_case.execute()

        mock_provider.get_current_track.return_value = None
        await use_case.execute()

        mock_publisher.clear.assert_awaited_once()
        assert use_case._last_track_hash is None

    @pytest.mark.asyncio
    async def test_execute_clears_when_track_not_playing(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track
        await use_case.execute()

        not_playing_track = Track(title="Test Song", artist="Test Artist", is_playing=False)
        mock_provider.get_current_track.return_value = not_playing_track
        await use_case.execute()

        mock_publisher.clear.assert_awaited_once()
        assert use_case._last_track_hash is None

    @pytest.mark.asyncio
    async def test_execute_no_clear_when_already_clear(self, use_case, mock_provider, mock_publisher):
        mock_provider.get_current_track.return_value = None

        await use_case.execute()
        await use_case.execute()

        mock_publisher.clear.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_wraps_provider_error(self, use_case, mock_provider):
        mock_provider.get_current_track.side_effect = Exception("API Error")

        with pytest.raises(ProviderError) as exc_info:
            await use_case.execute()

        assert "API Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_wraps_publisher_error_on_update(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track
        mock_publisher.update.side_effect = Exception("Discord Error")

        with pytest.raises(PublisherError) as exc_info:
            await use_case.execute()

        assert "Discord Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_wraps_publisher_error_on_clear(self, use_case, mock_provider, mock_publisher, sample_track):
        mock_provider.get_current_track.return_value = sample_track
        await use_case.execute()

        mock_provider.get_current_track.return_value = None
        mock_publisher.clear.side_effect = Exception("Clear Error")

        with pytest.raises(PublisherError) as exc_info:
            await use_case.execute()

        assert "Clear Error" in str(exc_info.value)