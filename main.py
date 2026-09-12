import asyncio
import sys
from config.settings import settings
from config.logging_config import setup_logging, get_logger
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.infrastructure.publishers.discord_rpc import DiscordRpcPublisher
from src.application.use_cases.sync_presence import SyncPresenceUseCase
from src.daemon.runner import DaemonRunner
from src.daemon.signal_handler import DaemonSignalHandler
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui.tray_app import run_tray_app
from src.presentation.gui.main_window import run_config_window

logger = get_logger(__name__)

_runner: DaemonRunner | None = None
_presence_publisher: DiscordRpcPublisher | None = None
_music_provider: LastFmClient | None = None
_signal_handler: DaemonSignalHandler | None = None


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

    repo = JsonConfigRepository()

    if not repo.is_configured():
        logger.info("Configuration not found, opening config window")
        run_config_window(on_save_callback=_start_tray)
    else:
        logger.info("Configuration found, starting tray app")
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