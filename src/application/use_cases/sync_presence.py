from src.domain.interfaces.music_provider import MusicProvider
from src.domain.interfaces.presence_publisher import PresencePublisher
from src.domain.entities.track import Track
from src.domain.exceptions import ProviderError, PublisherError
from config.logging_config import get_logger


logger = get_logger(__name__)


class SyncPresenceUseCase:
    def __init__(
        self,
        music_provider: MusicProvider,
        presence_publisher: PresencePublisher,
    ) -> None:
        self._music_provider = music_provider
        self._presence_publisher = presence_publisher
        self._last_track_hash: str | None = None

    async def execute(self) -> None:
        try:
            current_track = await self._music_provider.get_current_track()
        except Exception as e:
            logger.error(f"Failed to get current track: {e}")
            raise ProviderError(f"Failed to get current track: {e}") from e

        if current_track is None or not current_track.is_playing:
            await self._handle_not_playing()
            return

        current_hash = current_track.hash_key
        if current_hash == self._last_track_hash:
            logger.debug("Track unchanged, skipping Discord update")
            return

        try:
            await self._presence_publisher.update(current_track)
            self._last_track_hash = current_hash
            logger.info(f"Updated Discord presence: {current_track.display_name}")
        except Exception as e:
            logger.error(f"Failed to update Discord presence: {e}")
            raise PublisherError(f"Failed to update Discord presence: {e}") from e

    async def _handle_not_playing(self) -> None:
        if self._last_track_hash is not None:
            try:
                await self._presence_publisher.clear()
                self._last_track_hash = None
                logger.info("Cleared Discord presence (nothing playing)")
            except Exception as e:
                logger.error(f"Failed to clear Discord presence: {e}")
                raise PublisherError(f"Failed to clear Discord presence: {e}") from e
        else:
            logger.debug("Nothing playing and presence already clear")