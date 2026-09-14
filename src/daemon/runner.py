import asyncio
from src.application.use_cases.sync_presence import SyncPresenceUseCase
from config.settings import settings
from config.logging_config import get_logger


logger = get_logger(__name__)


class DaemonRunner:
    def __init__(
        self,
        use_case: SyncPresenceUseCase,
        interval: int | None = None,
    ) -> None:
        self._use_case = use_case
        self._custom_interval = interval
        self._shutdown_requested = False
        self._shutdown_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def _interval(self) -> int:
        return self._custom_interval if self._custom_interval is not None else settings.poll_interval

    def request_shutdown(self) -> None:
        logger.info("Shutdown requested")
        self._shutdown_requested = True
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        else:
            self._shutdown_event.set()

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        logger.info(f"Starting daemon with poll interval: {self._interval}s")

        while not self._shutdown_requested:
            try:
                await self._use_case.execute()
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}", exc_info=True)

            if self._shutdown_requested:
                break

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                continue

        logger.info("Daemon loop stopped")