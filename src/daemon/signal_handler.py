import signal
import asyncio
from typing import Optional
from src.daemon.runner import DaemonRunner
from config.logging_config import get_logger


logger = get_logger(__name__)


class DaemonSignalHandler:
    def __init__(self, runner: DaemonRunner) -> None:
        self._runner = runner
        self._shutdown_event = asyncio.Event()
        self._original_handlers: dict[int, signal.Handlers] = {}

    def setup(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for sig in (signal.SIGINT, signal.SIGTERM):
            self._original_handlers[sig] = signal.signal(sig, self._handle_signal)

        logger.info("Signal handlers registered for SIGINT and SIGTERM")

    def _handle_signal(self, signum: int, frame: Optional[object]) -> None:
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
        self._runner.request_shutdown()

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def restore(self) -> None:
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        logger.debug("Original signal handlers restored")