import customtkinter as ctk
import threading
import sys
import httpx
from pathlib import Path
from PIL import Image
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from config.logging_config import get_logger

logger = get_logger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _get_assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
        if (base_dir / "src" / "presentation" / "gui" / "assets").exists():
            return base_dir / "src" / "presentation" / "gui" / "assets"
        elif (base_dir / "assets").exists():
            return base_dir / "assets"
    return Path(__file__).parent / "assets"


class ConfigWindow:
    _active_instance: "ConfigWindow | None" = None
    _lock = threading.Lock()

    def __init__(self, on_save_callback=None) -> None:
        self._on_save_callback = on_save_callback
        self._saved = False
        self._repo = JsonConfigRepository()
        self._config = self._repo.load()
        self._root: ctk.CTk | None = None
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._toggle_btns: dict[str, ctk.CTkButton] = {}
        self._status_label: ctk.CTkLabel | None = None
        self._save_btn: ctk.CTkButton | None = None
        self._test_btn: ctk.CTkButton | None = None

    def focus(self) -> None:
        if self._root:
            try:
                self._root.event_generate("<<FocusWindow>>", when="tail")
            except Exception as e:
                logger.warning(f"Error focusing window: {e}")

    def _bring_to_front(self, event=None) -> None:
        if self._root:
            try:
                self._root.deiconify()
                self._root.lift()
                self._root.focus_force()
                self._root.attributes("-topmost", True)
                self._root.after(100, lambda: self._root.attributes("-topmost", False) if self._root else None)
            except Exception as e:
                logger.warning(f"Error bringing window to front: {e}")

    def show(self) -> bool:
        with ConfigWindow._lock:
            if ConfigWindow._active_instance is not None:
                logger.info("Config window is already open. Bringing existing instance to front.")
                ConfigWindow._active_instance.focus()
                return False
            ConfigWindow._active_instance = self

        try:
            self._saved = False
            self._root = ctk.CTk()
            self._root.title("LastfmPresence - Configuración")
            self._root.geometry("540x660")
            self._root.resizable(False, False)
            self._root.configure(fg_color="#0F1015")
            self._root.protocol("WM_DELETE_WINDOW", self._on_close)
            self._root.bind("<<FocusWindow>>", self._bring_to_front)
            self._root.bind("<<CloseWindow>>", lambda e: self._on_close())

            icon_path = _get_assets_dir() / "icon.ico"
            if icon_path.exists():
                try:
                    self._root.iconbitmap(str(icon_path))
                except Exception as e:
                    logger.warning(f"Could not set window icon: {e}")

            self._build_ui(icon_path)
            self._root.mainloop()
            return self._saved
        finally:
            with ConfigWindow._lock:
                if ConfigWindow._active_instance is self:
                    ConfigWindow._active_instance = None

    def _build_ui(self, icon_path: Path) -> None:
        main_frame = ctk.CTkFrame(
            self._root,
            corner_radius=16,
            fg_color="#1A1C24",
            border_color="#2A2D3D",
            border_width=1,
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(pady=(18, 10))

        if icon_path.exists():
            try:
                pil_icon = Image.open(icon_path)
                ctk_icon = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(48, 48))
                logo_label = ctk.CTkLabel(header_frame, image=ctk_icon, text="")
                logo_label.pack(pady=(0, 6))
            except Exception as e:
                logger.warning(f"Failed to render header logo: {e}")

        title_label = ctk.CTkLabel(
            header_frame,
            text="LastfmPresence",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#00F5D4",
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Configuración de Last.fm + Discord Rich Presence",
            font=ctk.CTkFont(size=12),
            text_color="#8F94A6",
        )
        subtitle_label.pack(pady=(2, 0))

        form_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=28, pady=8)

        fields = [
            ("lastfm_username", "Usuario Last.fm", False),
            ("lastfm_api_key", "API Key Last.fm", True),
            ("discord_client_id", "Discord Client ID", True),
            ("poll_interval", "Intervalo de sondeo (seg)", False),
        ]

        for key, label_text, is_secret in fields:
            self._create_field(form_frame, key, label_text, is_secret)

        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=28, pady=(16, 8))

        self._test_btn = ctk.CTkButton(
            buttons_frame,
            text="Probar Conexión",
            command=self._on_test_connection,
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#222532",
            hover_color="#2C3040",
            text_color="#E1E4ED",
            corner_radius=10,
            border_color="#2A2D3D",
            border_width=1,
        )
        self._test_btn.pack(side="left", padx=(0, 8), fill="x", expand=True)

        self._save_btn = ctk.CTkButton(
            buttons_frame,
            text="Guardar e Iniciar",
            command=self._on_save,
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#00F5D4",
            hover_color="#00D2B4",
            text_color="#090B10",
            corner_radius=10,
        )
        self._save_btn.pack(side="right", padx=(8, 0), fill="x", expand=True)

        self._status_label = ctk.CTkLabel(
            main_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#8F94A6",
            wraplength=440,
        )
        self._status_label.pack(pady=(6, 10))

        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.pack(pady=(0, 15))

        lastfm_link = ctk.CTkLabel(
            links_frame,
            text="Obtener API Key Last.fm",
            font=ctk.CTkFont(size=11, underline=True),
            text_color="#00F5D4",
            cursor="hand2",
        )
        lastfm_link.pack(side="left", padx=12)
        lastfm_link.bind("<Button-1>", lambda e: self._open_url("https://www.last.fm/api/account/create"))

        discord_link = ctk.CTkLabel(
            links_frame,
            text="Crear App Discord",
            font=ctk.CTkFont(size=11, underline=True),
            text_color="#5865F2",
            cursor="hand2",
        )
        discord_link.pack(side="left", padx=12)
        discord_link.bind("<Button-1>", lambda e: self._open_url("https://discord.com/developers/applications"))

    def _create_field(self, parent: ctk.CTkFrame, key: str, label_text: str, is_secret: bool) -> None:
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", pady=6)

        label = ctk.CTkLabel(
            field_frame,
            text=label_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#D0D4E0",
            anchor="w",
        )
        label.pack(fill="x", pady=(0, 3))

        input_container = ctk.CTkFrame(field_frame, fg_color="transparent")
        input_container.pack(fill="x")

        entry = ctk.CTkEntry(
            input_container,
            placeholder_text=label_text,
            show="*" if is_secret else "",
            height=38,
            font=ctk.CTkFont(size=13),
            corner_radius=8,
            fg_color="#13141C",
            border_color="#2A2D3D",
            text_color="#FFFFFF",
            placeholder_text_color="#55596B",
        )
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, str(self._config.get(key, "")))
        self._entries[key] = entry

        if is_secret:
            toggle_btn = ctk.CTkButton(
                input_container,
                text="👁",
                width=38,
                height=38,
                fg_color="#13141C",
                hover_color="#222532",
                border_color="#2A2D3D",
                border_width=1,
                corner_radius=8,
                text_color="#8F94A6",
                command=lambda k=key: self._toggle_secret_visibility(k),
            )
            toggle_btn.pack(side="right", padx=(6, 0))
            self._toggle_btns[key] = toggle_btn

    def _toggle_secret_visibility(self, key: str) -> None:
        entry = self._entries.get(key)
        btn = self._toggle_btns.get(key)
        if entry and btn:
            current_show = entry.cget("show")
            if current_show == "*":
                entry.configure(show="")
                btn.configure(text="🙈", text_color="#00F5D4")
            else:
                entry.configure(show="*")
                btn.configure(text="👁", text_color="#8F94A6")

    def _destroy_root(self) -> None:
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception as e:
                logger.warning(f"Error destroying window: {e}")
            finally:
                self._root = None

    def _on_save(self) -> None:
        new_config = {}
        for key, entry in self._entries.items():
            value = entry.get().strip()
            if key == "poll_interval":
                try:
                    new_config[key] = int(value) if value else 30
                except ValueError:
                    self._set_status("Intervalo debe ser un número entero", error=True)
                    return
            else:
                new_config[key] = value

        required = ["lastfm_username", "lastfm_api_key", "discord_client_id"]
        missing = [k for k in required if not new_config.get(k)]
        if missing:
            self._set_status(f"Campos obligatorios vacíos: {', '.join(missing)}", error=True)
            return

        self._repo.save(new_config)
        self._set_status("Configuración guardada correctamente", error=False)
        self._saved = True

        if self._on_save_callback:
            self._root.after(300, lambda: (self._destroy_root(), self._on_save_callback()))
        else:
            self._root.after(300, self._destroy_root)

    def _on_test_connection(self) -> None:
        self._test_btn.configure(state="disabled", text="Probando...")
        self._set_status("Probando credenciales...", error=False)

        def test_thread():
            try:
                config = {k: v.get().strip() for k, v in self._entries.items()}
                username = config.get("lastfm_username", "")
                api_key = config.get("lastfm_api_key", "")

                if not username or not api_key:
                    self._root.after(0, lambda: self._set_status("Usuario y API Key son requeridos", error=True))
                    self._root.after(0, lambda: self._test_btn.configure(state="normal", text="Probar Conexión"))
                    return

                url = "https://ws.audioscrobbler.com/2.0/"
                params = {
                    "method": "user.getRecentTracks",
                    "user": username,
                    "api_key": api_key,
                    "format": "json",
                    "limit": 1,
                }

                with httpx.Client(timeout=10.0) as client:
                    response = client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    if "error" in data:
                        self._root.after(0, lambda: self._set_status(f"Error Last.fm: {data.get('message', 'Desconocido')}", error=True))
                    else:
                        self._root.after(0, lambda: self._set_status("Conexión exitosa con Last.fm", error=False))
                else:
                    self._root.after(0, lambda: self._set_status(f"HTTP {response.status_code}: Credenciales inválidas", error=True))

            except httpx.TimeoutException:
                self._root.after(0, lambda: self._set_status("Timeout: Verifica tu conexión a internet", error=True))
            except Exception as e:
                self._root.after(0, lambda: self._set_status(f"Error: {str(e)}", error=True))
            finally:
                self._root.after(0, lambda: self._test_btn.configure(state="normal", text="Probar Conexión"))

        threading.Thread(target=test_thread, daemon=True).start()

    def _set_status(self, message: str, error: bool) -> None:
        if self._status_label:
            color = "#FF5566" if error else "#00F5D4"
            self._status_label.configure(text=message, text_color=color)

    def _on_close(self) -> None:
        self._saved = False
        self._destroy_root()

    @staticmethod
    def _open_url(url: str) -> None:
        import webbrowser
        webbrowser.open(url)


def run_config_window(on_save_callback=None) -> bool:
    window = ConfigWindow(on_save_callback)
    return window.show()