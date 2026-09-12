import customtkinter as ctk
import threading
import httpx
from pathlib import Path
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from config.logging_config import get_logger

logger = get_logger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConfigWindow:
    def __init__(self, on_save_callback=None) -> None:
        self._on_save_callback = on_save_callback
        self._repo = JsonConfigRepository()
        self._config = self._repo.load()
        self._root: ctk.CTk | None = None
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._status_label: ctk.CTkLabel | None = None
        self._save_btn: ctk.CTkButton | None = None
        self._test_btn: ctk.CTkButton | None = None

    def show(self) -> None:
        self._root = ctk.CTk()
        self._root.title("LastfmPresence - Configuración")
        self._root.geometry("520x580")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._root.mainloop()

    def _build_ui(self) -> None:
        main_frame = ctk.CTkFrame(self._root, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = ctk.CTkLabel(
            main_frame,
            text="LastfmPresence",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=("#1DB954", "#1DB954"),
        )
        title_label.pack(pady=(25, 5))

        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="Configuración de Last.fm + Discord Rich Presence",
            font=ctk.CTkFont(size=13),
            text_color=("gray60", "gray40"),
        )
        subtitle_label.pack(pady=(0, 25))

        form_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=30, pady=10)

        fields = [
            ("lastfm_username", "Usuario Last.fm", False),
            ("lastfm_api_key", "API Key Last.fm", True),
            ("discord_client_id", "Discord Client ID", False),
            ("poll_interval", "Intervalo de sondeo (seg)", False),
        ]

        for key, label_text, is_secret in fields:
            self._create_field(form_frame, key, label_text, is_secret)

        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=30, pady=(20, 10))

        self._test_btn = ctk.CTkButton(
            buttons_frame,
            text="Probar Conexión",
            command=self._on_test_connection,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color=("#3A3A3A", "#3A3A3A"),
            hover_color=("#4A4A4A", "#4A4A4A"),
        )
        self._test_btn.pack(side="left", padx=(0, 10), fill="x", expand=True)

        self._save_btn = ctk.CTkButton(
            buttons_frame,
            text="Guardar e Iniciar",
            command=self._on_save,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#1DB954", "#1DB954"),
            hover_color=("#1ED760", "#1ED760"),
        )
        self._save_btn.pack(side="right", padx=(10, 0), fill="x", expand=True)

        self._status_label = ctk.CTkLabel(
            main_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray60", "gray40"),
            wraplength=420,
        )
        self._status_label.pack(pady=(10, 20))

        links_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        links_frame.pack(pady=(0, 15))

        lastfm_link = ctk.CTkLabel(
            links_frame,
            text="Obtener API Key Last.fm",
            font=ctk.CTkFont(size=11, underline=True),
            text_color=("#1DB954", "#1DB954"),
            cursor="hand2",
        )
        lastfm_link.pack(side="left", padx=10)
        lastfm_link.bind("<Button-1>", lambda e: self._open_url("https://www.last.fm/api/account/create"))

        discord_link = ctk.CTkLabel(
            links_frame,
            text="Crear App Discord",
            font=ctk.CTkFont(size=11, underline=True),
            text_color=("#5865F2", "#5865F2"),
            cursor="hand2",
        )
        discord_link.pack(side="left", padx=10)
        discord_link.bind("<Button-1>", lambda e: self._open_url("https://discord.com/developers/applications"))

    def _create_field(self, parent: ctk.CTkFrame, key: str, label_text: str, is_secret: bool) -> None:
        field_frame = ctk.CTkFrame(parent, fg_color="transparent")
        field_frame.pack(fill="x", pady=8)

        label = ctk.CTkLabel(
            field_frame,
            text=label_text,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        label.pack(fill="x", pady=(0, 4))

        entry = ctk.CTkEntry(
            field_frame,
            placeholder_text=label_text,
            show="*" if is_secret else "",
            height=38,
            font=ctk.CTkFont(size=13),
            corner_radius=8,
        )
        entry.pack(fill="x")
        entry.insert(0, str(self._config.get(key, "")))
        self._entries[key] = entry

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

        if self._on_save_callback:
            self._root.after(500, lambda: (self._root.destroy(), self._on_save_callback()))

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
            color = ("#FF6B6B", "#FF6B6B") if error else ("#1DB954", "#1DB954")
            self._status_label.configure(text=message, text_color=color)

    def _on_close(self) -> None:
        if self._root:
            self._root.destroy()

    @staticmethod
    def _open_url(url: str) -> None:
        import webbrowser
        webbrowser.open(url)


def run_config_window(on_save_callback=None) -> None:
    window = ConfigWindow(on_save_callback)
    window.show()