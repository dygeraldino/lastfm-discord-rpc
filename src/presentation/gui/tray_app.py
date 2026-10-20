"""System tray entry point and window orchestration."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from config.logging_config import get_logger, get_logs_dir
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui.locale import t
from src.presentation.gui.main_window import run_config_window
from src.presentation.gui.player_window import PlayerWindow, run_player_window

logger = get_logger(__name__)


def _create_default_icon() -> Image.Image:
    """Fallback vinyl mark, drawn without relying on emoji fonts."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    mint = (111, 255, 228, 255)
    ink = (6, 13, 11, 255)
    draw.ellipse([5, 5, 59, 59], fill=ink)
    draw.ellipse([9, 9, 55, 55], fill=mint)
    draw.ellipse([23, 23, 41, 41], fill=ink)
    draw.ellipse([30, 30, 34, 34], fill=mint)
    return image


def _get_assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
        if (base_dir / "src" / "presentation" / "gui" / "assets").exists():
            return base_dir / "src" / "presentation" / "gui" / "assets"
        elif (base_dir / "assets").exists():
            return base_dir / "assets"
    return Path(__file__).parent / "assets"


def _load_tray_icon() -> Image.Image:
    assets_dir = _get_assets_dir()
    icon_path = assets_dir / "icon.ico"
    if icon_path.exists():
        try:
            return Image.open(icon_path)
        except Exception as e:
            logger.warning(f"Failed to load icon.ico: {e}")
    return _create_default_icon()


class TrayApp:
    def __init__(
        self,
        daemon_runner_coro: Callable[[], asyncio.coroutines.Coroutine],
        shutdown_callback: Callable[[], None],
    ) -> None:
        self._daemon_runner_coro = daemon_runner_coro
        self._shutdown_callback = shutdown_callback
        self._icon: Optional[pystray.Icon] = None
        self._daemon_thread: Optional[threading.Thread] = None
        self._player_thread: Optional[threading.Thread] = None
        self._running = False
        self._repo = JsonConfigRepository()

    # ------------------------------------------------------------ lifecycle --
    def run(self) -> None:
        self._running = True
        self._start_daemon_thread()
        self._setup_tray()
        assert self._icon is not None
        self._icon.run()

    def _start_daemon_thread(self) -> None:
        def run_daemon_loop() -> None:
            try:
                asyncio.run(self._daemon_runner_coro())
            except Exception:
                logger.exception("Daemon thread error")

        self._daemon_thread = threading.Thread(
            target=run_daemon_loop, daemon=True, name="DaemonThread"
        )
        self._daemon_thread.start()
        logger.info("Daemon thread started")

    def _stop_daemon_thread(self) -> None:
        if self._daemon_thread and self._daemon_thread.is_alive():
            logger.info("Stopping existing daemon thread...")
            self._shutdown_callback()
            self._daemon_thread.join(timeout=5.0)
            if self._daemon_thread.is_alive():
                logger.warning("Daemon thread did not terminate within 5 seconds")
            self._daemon_thread = None

    def _restart_daemon_thread(self) -> None:
        self._stop_daemon_thread()
        self._start_daemon_thread()

    # ---------------------------------------------------------------- tray ---
    def _setup_tray(self) -> None:
        icon_image = _load_tray_icon()

        menu = pystray.Menu(
            pystray.MenuItem(
                t("Abrir reproductor"),
                self._on_player_click,
                default=True,
            ),
            pystray.MenuItem(t("Ajustes"), self._on_config_click),
            pystray.MenuItem(t("Abrir logs"), self._on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("Buscar actualizaciones"), self._on_check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("Salir"), self._on_exit),
        )

        self._icon = pystray.Icon(
            "LastfmPresence",
            icon_image,
            t("LastfmPresence - Reproductor de Last.fm"),
            menu,
        )

    # ------------------------------------------------------------- handlers --
    def _on_player_click(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._show_player()

    def _show_player(self) -> None:
        logger.info("Opening player window from tray")
        if PlayerWindow.request_show():
            return

        if self._player_thread is not None and self._player_thread.is_alive():
            return

        self._player_thread = threading.Thread(
            target=self._run_player_window,
            daemon=True,
            name="PlayerWindow",
        )
        self._player_thread.start()

    def _run_player_window(self) -> None:
        run_player_window(
            on_open_config=self._open_config,
            on_config_saved=self._on_config_saved,
        )

    def _on_config_click(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._open_config()

    def _open_config(self) -> None:
        """Route Ajustes through the player's Tk loop; thread only when it is closed."""
        logger.info("Opening settings window")
        if PlayerWindow._instance is not None:
            PlayerWindow.request_open_config(self._on_config_saved)
            return

        threading.Thread(
            target=lambda: run_config_window(on_save_callback=self._on_config_saved),
            daemon=True,
            name="ConfigWindow",
        ).start()

    def _on_config_saved(self) -> None:
        logger.info("Config saved, restarting daemon...")
        from config.settings import reload_settings

        reload_settings()
        self._restart_daemon_thread()
        PlayerWindow.request_refresh()

    def _on_open_logs(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logs_dir = get_logs_dir()
        if logs_dir.exists():
            if sys.platform == "win32":
                os.startfile(logs_dir)
            else:
                subprocess.Popen(["xdg-open", str(logs_dir)])
        else:
            logger.warning("Logs directory does not exist")

    def _on_check_updates(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        webbrowser.open("https://github.com/dygeraldino/lastfm-discord-rpc/releases")

    def _on_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Exit requested from tray")
        self._running = False
        self._stop_daemon_thread()
        if self._icon:
            self._icon.stop()


def run_tray_app(
    daemon_runner_coro: Callable[[], asyncio.coroutines.Coroutine],
    shutdown_callback: Callable[[], None],
) -> None:
    app = TrayApp(daemon_runner_coro, shutdown_callback)
    app.run()
