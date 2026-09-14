import json
import os
from pathlib import Path
from typing import Any, Optional
from config.logging_config import get_logger

logger = get_logger(__name__)

APP_CONFIG_DIR = "LastfmPresence"
CONFIG_DIR = Path(os.getenv("APPDATA", "")) / APP_CONFIG_DIR
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "lastfm_username": "",
    "lastfm_api_key": "",
    "discord_client_id": "",
    "poll_interval": 30,
    "enable_rich_presence_buttons": True,
    "enable_fallback_artwork": True,
}


class JsonConfigRepository:
    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path or CONFIG_FILE
        self._config_dir = self._config_path.parent

    def _ensure_dir(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        self._ensure_dir()
        if not self._config_path.exists():
            logger.info(f"Config file not found at {self._config_path}, returning defaults")
            return DEFAULT_CONFIG.copy()

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            logger.info("Configuration loaded from %s", self._config_path)
            return merged
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load config: {e}, returning defaults")
            return DEFAULT_CONFIG.copy()

    def save(self, config: dict[str, Any]) -> None:
        self._ensure_dir()
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved to %s", self._config_path)
            from config.settings import reload_settings
            reload_settings()
        except OSError as e:
            logger.error(f"Failed to save config: {e}")
            raise

    def is_configured(self) -> bool:
        config = self.load()
        required = ["lastfm_username", "lastfm_api_key", "discord_client_id"]
        return all(config.get(key) for key in required)

    def get_config_path(self) -> Path:
        return self._config_path

    def get_logs_dir(self) -> Path:
        return self._config_dir / "logs"