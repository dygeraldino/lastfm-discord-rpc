import json
import os
from pathlib import Path
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from pydantic.fields import FieldInfo


APP_CONFIG_DIR = "LastfmPresence"


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._config_path = Path(os.getenv("APPDATA", "")) / APP_CONFIG_DIR / "config.json"

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        if not self._config_path.exists():
            return None, field_name, False

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            value = data.get(field_name)
            if value is not None:
                return value, field_name, True
        except (json.JSONDecodeError, OSError):
            pass
        return None, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        return value

    def __call__(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            JsonConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def reload_settings() -> Settings:
    global settings
    new_settings = get_settings()
    for field_name in type(settings).model_fields:
        setattr(settings, field_name, getattr(new_settings, field_name))
    return settings