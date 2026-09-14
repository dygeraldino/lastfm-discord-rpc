import asyncio
from pypresence import Presence, ActivityType
from pypresence.exceptions import DiscordNotFound, PipeClosed, InvalidID
from src.domain.interfaces.presence_publisher import PresencePublisher
from src.domain.entities.track import Track
from src.domain.exceptions import PublisherError
from config.settings import settings
from config.logging_config import get_logger


logger = get_logger(__name__)


class DiscordRpcPublisher(PresencePublisher):
    def __init__(self) -> None:
        self._client: Presence | None = None
        self._override_client_id: str | None = None
        self._connected = False
        self._reconnect_task: asyncio.Task | None = None

    @property
    def _client_id(self) -> str:
        if self._override_client_id is not None:
            return self._override_client_id
        return settings.discord_client_id

    @_client_id.setter
    def _client_id(self, value: str) -> None:
        self._override_client_id = value

    async def connect(self) -> None:
        if self._connected and self._client:
            return

        client_id = self._client_id
        if not client_id:
            logger.warning("Discord Client ID is empty, will retry on next update")
            self._connected = False
            return

        try:
            self._client = Presence(client_id)
            await asyncio.to_thread(self._client.connect)
            self._connected = True
            logger.info("Connected to Discord RPC")
        except DiscordNotFound:
            logger.warning("Discord client not found, will retry on next update")
            self._connected = False
        except InvalidID:
            logger.error("Invalid Discord Client ID")
            raise PublisherError("Invalid Discord Client ID")
        except Exception as e:
            logger.debug(f"Discord connection error: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._client and self._connected:
            try:
                await asyncio.to_thread(self._client.close)
                logger.info("Disconnected from Discord RPC")
            except Exception as e:
                logger.error(f"Error disconnecting from Discord: {e}")
            finally:
                self._connected = False
                self._client = None

    async def update(self, track: Track) -> None:
        if not self._connected:
            await self._try_reconnect()
            if not self._connected:
                raise PublisherError("Discord not connected")

        try:
            await self._do_update(track)
        except (PipeClosed, DiscordNotFound) as e:
            logger.warning(f"Discord connection lost: {e}, attempting reconnect")
            self._connected = False
            await self._try_reconnect()
            if self._connected:
                await self._do_update(track)
            else:
                raise PublisherError("Discord reconnection failed") from e

    async def _do_update(self, track: Track) -> None:
        if not self._client:
            raise PublisherError("Discord client not initialized")

        large_image = track.artwork_url if track.artwork_url else None
        large_text = track.album[:128] if (large_image and track.album) else None

        kwargs = {
            "activity_type": ActivityType.LISTENING,
            "details": track.title[:128],
            "state": f"by {track.artist}"[:128],
            "small_image": "lastfm",
            "small_text": "Last.fm",
            "start": int(track.timestamp.timestamp()) if track.timestamp else None,
        }
        if large_image:
            kwargs["large_image"] = large_image
        if large_text:
            kwargs["large_text"] = large_text

        if settings.enable_rich_presence_buttons and track.button_urls:
            kwargs["buttons"] = [
                {"label": label[:32], "url": url}
                for label, url in track.button_urls[:2]
            ]

        await asyncio.to_thread(lambda: self._client.update(**kwargs))

    async def clear(self) -> None:
        if not self._connected or not self._client:
            return

        try:
            await asyncio.to_thread(self._client.clear)
            logger.debug("Cleared Discord presence")
        except (PipeClosed, DiscordNotFound):
            self._connected = False
            logger.warning("Discord connection lost while clearing")
        except Exception as e:
            logger.error(f"Error clearing Discord presence: {e}")
            raise PublisherError(f"Failed to clear presence: {e}") from e

    async def _try_reconnect(self) -> None:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.connect()
                if self._connected:
                    return
            except Exception as e:
                logger.debug(f"Reconnect attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error("Failed to reconnect to Discord after max retries")