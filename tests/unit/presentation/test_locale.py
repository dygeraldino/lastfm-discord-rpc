import json
from unittest.mock import patch, MagicMock
import pytest

from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui.locale import (
    TRANSLATIONS,
    get_language,
    load_language,
    normalize_language,
    save_language,
    set_language,
    t,
)


class TestLocale:
    def setup_method(self):
        # Reset to default Spanish before each test
        set_language("es")

    def test_normalize_language(self):
        assert normalize_language("es") == "es"
        assert normalize_language("ES") == "es"
        assert normalize_language("Español") == "es"
        assert normalize_language("español") == "es"
        assert normalize_language("spanish") == "es"

        assert normalize_language("en") == "en"
        assert normalize_language("EN") == "en"
        assert normalize_language("English") == "en"
        assert normalize_language("english") == "en"
        assert normalize_language("inglés") == "en"
        assert normalize_language("ingles") == "en"

        assert normalize_language(None) == "es"
        assert normalize_language("") == "es"
        assert normalize_language("fr") == "es"

    def test_set_and_get_language(self):
        set_language("en")
        assert get_language() == "en"

        set_language("English")
        assert get_language() == "en"

        set_language("es")
        assert get_language() == "es"

        set_language("Español")
        assert get_language() == "es"

    def test_translate_spanish_identity(self):
        set_language("es")
        assert t("Ajustes") == "Ajustes"
        assert t("Conexión") == "Conexión"
        assert t("hace {minutes} min", minutes=5) == "hace 5 min"

    def test_translate_english(self):
        set_language("en")
        assert t("Ajustes") == "Settings"
        assert t("Conexión") == "Connection"
        assert t("Abrir reproductor") == "Open player"
        assert t("hace {minutes} min", minutes=12) == "12 min ago"
        assert t("Idioma") == "Language"
        assert t("Idioma de la interfaz.") == "Interface language."
        assert t("Faltan datos: ") == "Missing data: "

    def test_translate_unknown_fallback(self):
        set_language("en")
        assert t("Frase no existente") == "Frase no existente"

    def test_load_language_from_config(self):
        with patch("src.presentation.gui.locale.JsonConfigRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load.return_value = {"language": "English"}
            MockRepo.return_value = mock_repo

            loaded = load_language()
            assert loaded == "en"
            assert get_language() == "en"

    def test_load_language_spanish_explicit(self):
        with patch("src.presentation.gui.locale.JsonConfigRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load.return_value = {"language": "es"}
            MockRepo.return_value = mock_repo

            loaded = load_language()
            assert loaded == "es"
            assert get_language() == "es"

    def test_load_language_default_from_config(self):
        with patch("src.presentation.gui.locale.JsonConfigRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.load.return_value = {"language": "en"}
            MockRepo.return_value = mock_repo

            loaded = load_language()
            assert loaded == "en"
            assert get_language() == "en"

    def test_save_language_persists_normalized(self):
        with patch("src.presentation.gui.locale.JsonConfigRepository") as MockRepo:
            mock_repo = MagicMock()
            saved_dict = {}
            mock_repo.load.return_value = saved_dict
            def fake_save(cfg):
                saved_dict.update(cfg)
            mock_repo.save.side_effect = fake_save
            MockRepo.return_value = mock_repo

            save_language("English")
            assert get_language() == "en"
            assert saved_dict["language"] == "en"

            save_language("Español")
            assert get_language() == "es"
            assert saved_dict["language"] == "es"

    def test_config_window_collects_normalized_language(self):
        from src.presentation.gui.main_window import ConfigWindow

        window = ConfigWindow()
        window._entries = {
            "lastfm_username": MagicMock(get=lambda: "user"),
            "lastfm_api_key": MagicMock(get=lambda: "key"),
            "discord_client_id": MagicMock(get=lambda: "id"),
            "poll_interval": MagicMock(get=lambda: "15"),
            "enable_fallback_artwork": MagicMock(get=lambda: 1),
            "language": MagicMock(get=lambda: "English"),
        }

        with patch.object(window._repo, "load", return_value={}):
            config, err = window._collect_config()
            assert err is None
            assert config["language"] == "en"

        window._entries["language"] = MagicMock(get=lambda: "Español")
        with patch.object(window._repo, "load", return_value={}):
            config, err = window._collect_config()
            assert err is None
            assert config["language"] == "es"

    def test_player_window_request_language_change(self):
        from src.presentation.gui.player_window import PlayerWindow

        PlayerWindow.request_language_change("en")
        assert not PlayerWindow._language_requests.empty()
        item = PlayerWindow._language_requests.get_nowait()
        assert item == "en"
