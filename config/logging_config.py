import sys
from pathlib import Path
from loguru import logger
from config.settings import settings


def setup_logging() -> None:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.remove()

    if sys.stdout is not None:
        logger.add(
            sys.stdout,
            level=settings.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True,
        )

    logger.add(
        log_dir / "daemon_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        encoding="utf-8",
    )


def get_logger(name: str):
    return logger.bind(name=name)