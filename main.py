import asyncio
import ctypes
import os
import sys
from pathlib import Path
from config.settings import settings, reload_settings
from config.logging_config import setup_logging, get_logger
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.infrastructure.publishers.discord_rpc import DiscordRpcPublisher
from src.application.use_cases.sync_presence import SyncPresenceUseCase
from src.daemon.runner import DaemonRunner
from src.daemon.signal_handler import DaemonSignalHandler
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui.tray_app import run_tray_app
from src.presentation.gui.main_window import run_config_window

# Ensure working directory is application folder when packaged
if getattr(sys, "frozen", False):
    try:
        os.chdir(Path(sys.executable).parent)
    except Exception:
        pass

logger = get_logger(__name__)

_MUTEX_NAME = "Global\\LastfmPresence_SingleInstance_Mutex_Guid_1029"
_mutex_handle = None

_runner: DaemonRunner | None = None
_presence_publisher: DiscordRpcPublisher | None = None
_music_provider: LastFmClient | None = None
_signal_handler: DaemonSignalHandler | None = None


def _ensure_single_instance() -> bool:
    global _mutex_handle
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
            last_error = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            if last_error == ERROR_ALREADY_EXISTS:
                return False
        except Exception as e:
            logger.warning(f"Failed to check mutex: {e}")
    return True


async def _daemon_main() -> None:
    global _runner, _presence_publisher, _music_provider, _signal_handler

    logger.info("Starting Last.fm Discord Rich Presence Daemon")

    _music_provider = LastFmClient()
    _presence_publisher = DiscordRpcPublisher()

    await _presence_publisher.connect()

    use_case = SyncPresenceUseCase(
        music_provider=_music_provider,
        presence_publisher=_presence_publisher,
    )

    _runner = DaemonRunner(use_case=use_case)
    _signal_handler = DaemonSignalHandler(_runner)
    _signal_handler.setup()

    try:
        await _runner.run()
    finally:
        logger.info("Shutting down daemon...")
        await _presence_publisher.clear()
        await _presence_publisher.disconnect()
        await _music_provider.close()
        _signal_handler.restore()
        logger.info("Daemon shutdown complete")


def _shutdown_all() -> None:
    if _runner:
        _runner.request_shutdown()


def _start_tray() -> None:
    run_tray_app(_daemon_main, _shutdown_all)


def main() -> None:
    setup_logging()

    if not _ensure_single_instance():
        logger.warning("Another instance of LastfmPresence is already running. Exiting cleanly.")
        sys.exit(0)

    repo = JsonConfigRepository()

    if not repo.is_configured():
        logger.info("Configuration not found, opening config window")
        saved = run_config_window()
        if not saved or not repo.is_configured():
            logger.info("Configuration window closed without saving required settings. Exiting cleanly.")
            sys.exit(0)

    logger.info("Configuration valid, starting tray app")
    reload_settings()
    _start_tray()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        _shutdown_all()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)