import asyncio
from config.settings import settings
from config.logging_config import setup_logging, get_logger
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.infrastructure.publishers.discord_rpc import DiscordRpcPublisher
from src.application.use_cases.sync_presence import SyncPresenceUseCase
from src.daemon.runner import DaemonRunner
from src.daemon.signal_handler import DaemonSignalHandler


logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Starting Last.fm Discord Rich Presence Daemon")

    music_provider = LastFmClient()
    presence_publisher = DiscordRpcPublisher()

    await presence_publisher.connect()

    use_case = SyncPresenceUseCase(
        music_provider=music_provider,
        presence_publisher=presence_publisher,
    )

    runner = DaemonRunner(use_case=use_case)
    signal_handler = DaemonSignalHandler(runner)
    signal_handler.setup()

    try:
        await runner.run()
    finally:
        logger.info("Shutting down...")
        await presence_publisher.clear()
        await presence_publisher.disconnect()
        await music_provider.close()
        signal_handler.restore()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass