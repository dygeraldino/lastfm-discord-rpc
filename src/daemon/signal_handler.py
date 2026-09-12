import signal
import asyncio
import threading
from typing import Optional
from src.daemon.runner import DaemonRunner
from config.logging_config import get_logger


logger = get_logger(__name__)


class DaemonSignalHandler:
    def __init__(self, runner: DaemonRunner) -> None:
        self._runner = runner
        self._shutdown_event = asyncio.Event()
        self._original_handlers: dict[int, signal.Handlers] = {}
        self._signals_registered = False

    def setup(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            logger.debug("Not in main thread, skipping signal handler registration")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._original_handlers[sig] = signal.signal(sig, self._handle_signal)
            except ValueError as e:
                logger.warning(f"Could not register signal handler for {sig}: {e}")
                return

        self._signals_registered = True
        logger.info("Signal handlers registered for SIGINT and SIGTERM")

    def _handle_signal(self, signum: int, frame: Optional[object]) -> None:
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
        self._runner.request_shutdown()

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def restore(self) -> None:
        if not self._signals_registered:
            return
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except ValueError:
                pass
        logger.debug("Original signal handlers restored")