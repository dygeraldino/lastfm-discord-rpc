from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lastfm_api_key: str = ""
    lastfm_username: str = ""
    discord_client_id: str = ""
    poll_interval: int = 30
    log_level: str = "INFO"
    enable_rich_presence_buttons: bool = True

    @property
    def lastfm_base_url(self) -> str:
        return "https://ws.audioscrobbler.com/2.0/"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()