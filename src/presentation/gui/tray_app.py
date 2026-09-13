import asyncio
import threading
import sys
import os
from pathlib import Path
from typing import Callable, Optional
import pystray
from PIL import Image, ImageDraw
from config.logging_config import get_logger, get_logs_dir
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui.main_window import run_config_window

logger = get_logger(__name__)


def _create_default_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(0, 245, 212, 255))
    draw.text((20, 18), "♪", fill=(11, 14, 20, 255), font_size=32)
    return img


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
        self._running = False
        self._repo = JsonConfigRepository()

    def run(self) -> None:
        self._running = True
        self._start_daemon_thread()
        self._setup_tray()
        self._icon.run()

    def _start_daemon_thread(self) -> None:
        def run_daemon_loop():
            try:
                asyncio.run(self._daemon_runner_coro())
            except Exception as e:
                logger.error(f"Daemon thread error: {e}", exc_info=True)

        self._daemon_thread = threading.Thread(target=run_daemon_loop, daemon=True, name="DaemonThread")
        self._daemon_thread.start()
        logger.info("Daemon thread started")

    def _setup_tray(self) -> None:
        icon_image = _load_tray_icon()

        menu = pystray.Menu(
            pystray.MenuItem("⚙️ Configuración", self._on_config_click, default=True),
            pystray.MenuItem("📋 Abrir Logs", self._on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🔄 Buscar actualizaciones", self._on_check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Salir", self._on_exit),
        )

        self._icon = pystray.Icon(
            "LastfmPresence",
            icon_image,
            "LastfmPresence - Last.fm → Discord",
            menu,
        )

    def _on_config_click(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Opening config window from tray")
        threading.Thread(target=self._run_config_window, daemon=True).start()

    def _run_config_window(self) -> None:
        def on_config_saved():
            logger.info("Config saved, restarting daemon...")
            from config.settings import reload_settings
            reload_settings()
            self._shutdown_callback()
            self._start_daemon_thread()

        run_config_window(on_save_callback=on_config_saved)

    def _on_open_logs(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logs_dir = get_logs_dir()
        if logs_dir.exists():
            if sys.platform == "win32":
                os.startfile(logs_dir)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(logs_dir)])
        else:
            logger.warning("Logs directory does not exist")

    def _on_check_updates(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        import webbrowser
        webbrowser.open("https://github.com/dygeraldino/lastfm-discord-rpc/releases")

    def _on_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Exit requested from tray")
        self._running = False
        self._shutdown_callback()
        if self._icon:
            self._icon.stop()


def run_tray_app(
    daemon_runner_coro: Callable[[], asyncio.coroutines.Coroutine],
    shutdown_callback: Callable[[], None],
) -> None:
    app = TrayApp(daemon_runner_coro, shutdown_callback)
    app.run()