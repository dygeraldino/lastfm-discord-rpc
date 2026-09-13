import json
import pytest
from pathlib import Path
from unittest.mock import patch
from config.settings import settings, reload_settings, JsonConfigSettingsSource
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.infrastructure.providers.lastfm_client import LastFmClient
from src.infrastructure.publishers.discord_rpc import DiscordRpcPublisher
from src.daemon.runner import DaemonRunner


def _mock_init(self, settings_cls, config_path):
    super(JsonConfigSettingsSource, self).__init__(settings_cls)
    self._config_path = config_path


def test_reload_settings_updates_in_place(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_data = {
        "lastfm_username": "new_user",
        "lastfm_api_key": "new_key",
        "discord_client_id": "123456789",
        "poll_interval": 15,
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    with patch.object(JsonConfigSettingsSource, "__init__", lambda self, cls: _mock_init(self, cls, config_file)):
        reload_settings()
        assert settings.lastfm_username == "new_user"
        assert settings.lastfm_api_key == "new_key"
        assert settings.discord_client_id == "123456789"
        assert settings.poll_interval == 15


def test_json_config_repository_save_triggers_reload(tmp_path: Path):
    config_file = tmp_path / "config.json"
    repo = JsonConfigRepository(config_path=config_file)

    with patch.object(JsonConfigSettingsSource, "__init__", lambda self, cls: _mock_init(self, cls, config_file)):
        repo.save({
            "lastfm_username": "repo_user",
            "lastfm_api_key": "repo_key",
            "discord_client_id": "987654321",
            "poll_interval": 20,
        })

        assert settings.lastfm_username == "repo_user"
        assert settings.lastfm_api_key == "repo_key"
        assert settings.discord_client_id == "987654321"
        assert settings.poll_interval == 20


def test_components_access_updated_settings(tmp_path: Path):
    config_file = tmp_path / "config.json"
    repo = JsonConfigRepository(config_path=config_file)

    with patch.object(JsonConfigSettingsSource, "__init__", lambda self, cls: _mock_init(self, cls, config_file)):
        repo.save({
            "lastfm_username": "dynamic_user",
            "lastfm_api_key": "dynamic_key",
            "discord_client_id": "555555555",
            "poll_interval": 45,
        })

        client = LastFmClient()
        publisher = DiscordRpcPublisher()
        runner = DaemonRunner(use_case=None)

        assert client._username == "dynamic_user"
        assert client._api_key == "dynamic_key"
        assert publisher._client_id == "555555555"
        assert runner._interval == 45
