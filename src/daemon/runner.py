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
        self._interval = interval or settings.poll_interval
        self._shutdown_requested = False
        self._shutdown_event = asyncio.Event()

    def request_shutdown(self) -> None:
        logger.info("Shutdown requested")
        self._shutdown_requested = True
        self._shutdown_event.set()

    async def run(self) -> None:
        logger.info(f"Starting daemon with poll interval: {self._interval}s")

        while not self._shutdown_requested:
            try:
                await self._use_case.execute()
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}", exc_info=True)

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                continue

        logger.info("Daemon loop stopped")