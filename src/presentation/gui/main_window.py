"""Settings window for LastfmPresence.

The player is the everyday surface; this window is reached from its gear (or
from the tray menu) and carries only the connection and behaviour controls.
"""

from __future__ import annotations

import threading
import webbrowser
from typing import Optional
import customtkinter as ctk
import httpx

from config.logging_config import get_logger
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.presentation.gui import theme
from src.presentation.gui.locale import t, get_language, set_language, save_language

logger = get_logger(__name__)

LASTFM_API_KEY_URL = "https://www.last.fm/api/account/create"
DISCORD_APPS_URL = "https://discord.com/developers/applications"


class ConfigWindow:
    _active_instance: "Optional[ConfigWindow]" = None
    _lock = threading.Lock()

    def __init__(self, on_save_callback=None, master=None) -> None:
        self._on_save_callback = on_save_callback
        self._master = master
        self._saved = False
        self._repo = JsonConfigRepository()
        self._config = self._repo.load()
        self._root: Optional[ctk.CTk] = None
        self._entries: dict[str, object] = {}
        self._toggle_btns: dict[str, ctk.CTkButton] = {}
        self._status_label: Optional[ctk.CTkLabel] = None
        self._save_btn: Optional[ctk.CTkButton] = None
        self._test_btn: Optional[ctk.CTkButton] = None

    # ------------------------------------------------------------ lifecycle --
    def focus(self) -> None:
        if self._root:
            try:
                self._root.event_generate("<<FocusWindow>>", when="tail")
            except Exception as e:
                logger.warning(f"Error focusing window: {e}")

    def _bring_to_front(self, event=None) -> None:
        if not self._root:
            return
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
            self._root.attributes("-topmost", True)
            self._root.after(
                100,
                lambda: self._root.attributes("-topmost", False) if self._root else None,
            )
        except Exception as e:
            logger.warning(f"Error bringing window to front: {e}")

    def show(self) -> bool:
        embedded = self._master is not None
        with ConfigWindow._lock:
            if ConfigWindow._active_instance is not None:
                logger.info("Config window is already open. Bringing existing instance to front.")
                ConfigWindow._active_instance.focus()
                return False
            ConfigWindow._active_instance = self

        try:
            self._saved = False
            if embedded:
                self._open_in_master()
                return True
            return self._open_standalone()
        finally:
            if not embedded:
                with ConfigWindow._lock:
                    if ConfigWindow._active_instance is self:
                        ConfigWindow._active_instance = None

    def _open_standalone(self) -> bool:
        window = ctk.CTk()
        self._root = window
        window.title("LastfmPresence - Ajustes")
        window.geometry("620x640")
        window.resizable(False, False)
        window.configure(fg_color=theme.INK)
        window.protocol("WM_DELETE_WINDOW", self._on_close)
        window.bind("<<FocusWindow>>", self._bring_to_front)
        window.bind("<Escape>", lambda _event: self._on_close())
        theme.set_window_icon(window)

        self._build_ui()
        self._center_window()
        window.mainloop()
        return self._saved

    def _open_in_master(self) -> None:
        """Host the window inside the player's Tk loop: one thread, no second mainloop."""
        master = self._master
        if master is None:
            return
        window = ctk.CTkToplevel(master)
        self._root = window
        window.title("LastfmPresence - Ajustes")
        window.geometry("620x640")
        window.resizable(False, False)
        window.configure(fg_color=theme.INK)
        window.transient(master)
        window.protocol("WM_DELETE_WINDOW", self._on_close)
        window.bind("<<FocusWindow>>", self._bring_to_front)
        window.bind("<Escape>", lambda _event: self._on_close())
        theme.set_window_icon(window)

        self._build_ui()
        self._center_window(over=master)
        window.lift()
        window.focus_force()

    def _center_window(self, over=None) -> None:
        if not self._root:
            return
        try:
            self._root.update_idletasks()
            width, height = 620, 640
            scale = ctk.ScalingTracker.get_window_scaling(self._root)
            physical_width = int(width * scale)
            physical_height = int(height * scale)
            if over is not None:
                x = over.winfo_rootx() + (over.winfo_width() - physical_width) // 2
                y = over.winfo_rooty() + (over.winfo_height() - physical_height) // 2
            else:
                screen_width = int(self._root.winfo_screenwidth() * scale)
                screen_height = int(self._root.winfo_screenheight() * scale)
                x = max(0, (screen_width - physical_width) // 2)
                y = max(0, (screen_height - physical_height) // 2 - 20)
            self._root.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _destroy_root(self) -> None:
        window = self._root
        self._root = None
        if not window:
            return
        try:
            if self._master is not None:
                window.destroy()
            else:
                window.quit()
                window.destroy()
        except Exception as e:
            logger.warning(f"Error destroying window: {e}")
        finally:
            with ConfigWindow._lock:
                if ConfigWindow._active_instance is self:
                    ConfigWindow._active_instance = None

    # ----------------------------------------------------------------- UI ----
    def _build_ui(self) -> None:
        assert self._root is not None
        root = self._root

        self._build_header(root)

        footer = ctk.CTkFrame(root, fg_color=theme.INK, corner_radius=0)
        footer.pack(side="bottom", fill="x", padx=32, pady=(8, 18))
        self._build_footer(footer)

        ctk.CTkFrame(root, height=1, fg_color=theme.BORDER, corner_radius=0).pack(
            side="bottom", fill="x"
        )

        body = ctk.CTkScrollableFrame(root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=(20, 0))
        self._build_form(body)

    def _build_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color=theme.INK, corner_radius=0, height=86)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32)

        logo = theme.app_icon_pil(34)
        if logo is not None:
            ctk.CTkLabel(inner, text="", image=theme.pil_to_ctk(logo, (34, 34))).pack(
                side="left", padx=(0, 14)
            )

        text = ctk.CTkFrame(inner, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text,
            text=t("Ajustes"),
            font=theme.font("display-lg", "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
        ).pack(fill="x")

        configured = bool(
            self._config.get("lastfm_username")
            and self._config.get("lastfm_api_key")
            and self._config.get("discord_client_id")
        )
        subtitle = (
            t("Conexión con Last.fm y Discord")
            if configured
            else t("Configura tu cuenta para empezar")
        )
        ctk.CTkLabel(
            text,
            text=subtitle,
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(parent, height=1, fg_color=theme.BORDER, corner_radius=0).pack(fill="x")

    def _build_form(self, parent) -> None:
        ctk.CTkLabel(
            parent,
            text=t("Conexión"),
            font=theme.font("body", "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            parent,
            text=t("Last.fm alimenta tu estado; Discord lo muestra."),
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        ).pack(fill="x", pady=(1, 12))

        self._add_text_field(
            parent,
            "lastfm_username",
            t("Usuario de Last.fm"),
        )
        self._add_text_field(
            parent,
            "lastfm_api_key",
            t("API Key de Last.fm"),
            secret=True,
            link=(t("Obtener API Key"), LASTFM_API_KEY_URL),
        )
        self._add_text_field(
            parent,
            "discord_client_id",
            t("Discord Client ID"),
            secret=True,
            link=(t("Crear aplicación"), DISCORD_APPS_URL),
        )

        ctk.CTkFrame(parent, height=1, fg_color=theme.BORDER, corner_radius=0).pack(
            fill="x", pady=(4, 18)
        )

        ctk.CTkLabel(
            parent,
            text=t("Comportamiento"),
            font=theme.font("body", "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            parent,
            text=t("Cómo se actualiza el estado en Discord."),
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        ).pack(fill="x", pady=(1, 12))

        self._add_poll_row(parent)
        self._add_fallback_row(parent)

    def _add_text_field(
        self,
        parent,
        key: str,
        label: str,
        secret: bool = False,
        link: Optional[tuple[str, str]] = None,
    ) -> None:
        current_value = str(self._config.get(key, "") or "")
        field = ctk.CTkFrame(parent, fg_color="transparent")
        field.pack(fill="x", pady=(0, 12))

        label_row = ctk.CTkFrame(field, fg_color="transparent")
        label_row.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            label_row,
            text=label,
            font=theme.font("small", "bold"),
            text_color=theme.LABEL,
            anchor="w",
            height=14,
        ).pack(side="left")

        if link is not None:
            link_text, url = link
            ctk.CTkButton(
                label_row,
                text=link_text,
                image=theme.icon("external", 10, theme.ACCENT),
                compound="right",
                command=lambda target=url: webbrowser.open(target),
                height=18,
                width=132,
                font=theme.font("small"),
                fg_color="transparent",
                hover_color=theme.HOVER,
                text_color=theme.ACCENT,
                corner_radius=6,
                border_width=0,
            ).pack(side="right")

        input_container = ctk.CTkFrame(field, fg_color="transparent")
        input_container.pack(fill="x")

        entry = ctk.CTkEntry(
            input_container,
            placeholder_text=label,
            show="*" if secret else "",
            height=38,
            font=theme.font("body"),
            corner_radius=8,
            fg_color=theme.PANEL,
            border_color=theme.BORDER,
            border_width=1,
            text_color=theme.PAPER,
            placeholder_text_color=theme.MUTED,
        )
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, current_value)
        self._entries[key] = entry

        entry.bind("<FocusIn>", lambda _event, w=entry: w.configure(border_color=theme.ACCENT))
        entry.bind("<FocusOut>", lambda _event, w=entry: w.configure(border_color=theme.BORDER))

        if secret:
            toggle = ctk.CTkButton(
                input_container,
                text=t("Mostrar"),
                width=68,
                height=38,
                fg_color="transparent",
                hover_color=theme.HOVER,
                corner_radius=8,
                font=theme.font("small"),
                text_color=theme.LABEL,
                command=lambda k=key: self._toggle_secret_visibility(k),
            )
            toggle.pack(side="right", padx=(8, 0))
            self._toggle_btns[key] = toggle

    def _add_poll_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text,
            text=t("Intervalo de consulta"),
            font=theme.font("small", "bold"),
            text_color=theme.PAPER,
            anchor="w",
            height=14,
        ).pack(fill="x")

        ctk.CTkLabel(
            text,
            text=t("Cada cuántos segundos se consulta Last.fm."),
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        ).pack(fill="x", pady=(1, 0))

        entry = ctk.CTkEntry(
            row,
            height=36,
            width=64,
            justify="center",
            font=theme.font(11),
            corner_radius=8,
            fg_color=theme.PANEL,
            border_color=theme.BORDER,
            border_width=1,
            text_color=theme.PAPER,
        )
        entry.pack(side="right", padx=(8, 0))
        entry.insert(0, str(self._config.get("poll_interval", 30)))
        self._entries["poll_interval"] = entry
        entry.bind("<FocusIn>", lambda _event, w=entry: w.configure(border_color=theme.ACCENT))
        entry.bind("<FocusOut>", lambda _event, w=entry: w.configure(border_color=theme.BORDER))

    def _add_fallback_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            text,
            text=t("Carátulas alternativas"),
            font=theme.font("small", "bold"),
            text_color=theme.PAPER,
            anchor="w",
            height=14,
        ).pack(fill="x")

        ctk.CTkLabel(
            text,
            text=t("Deezer y MusicBrainz cuando Last.fm no trae portada."),
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        ).pack(fill="x", pady=(1, 0))

        switch = ctk.CTkSwitch(
            row,
            text="",
            width=44,
            progress_color=theme.ACCENT,
            button_color=theme.PAPER,
            button_hover_color="#FFFFFF",
            fg_color=theme.BORDER,
        )
        switch.pack(side="right", padx=(12, 0))
        current_value = self._config.get("enable_fallback_artwork", True)
        if current_value in (True, "true", "True", "1", 1):
            switch.select()
        else:
            switch.deselect()
        self._entries["enable_fallback_artwork"] = switch

        # --- Idioma / Language ---
        lang_row = ctk.CTkFrame(parent, fg_color="transparent")
        lang_row.pack(fill="x", pady=(18, 0))

        lang_text = ctk.CTkFrame(lang_row, fg_color="transparent")
        lang_text.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            lang_text,
            text=t("Idioma"),
            font=theme.font("small", "bold"),
            text_color=theme.PAPER,
            anchor="w",
            height=14,
        ).pack(fill="x")

        ctk.CTkLabel(
            lang_text,
            text=t("Idioma de la interfaz."),
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        ).pack(fill="x", pady=(1, 0))

        current_lang = get_language()
        lang_display = "Español" if current_lang == "es" else "English"

        lang_menu = ctk.CTkOptionMenu(
            lang_row,
            values=["Español", "English"],
            command=self._on_language_change,
            width=120,
            font=theme.font("small"),
            fg_color=theme.PANEL,
            button_color=theme.BORDER,
            button_hover_color=theme.HOVER,
            text_color=theme.PAPER,
            dropdown_fg_color=theme.PANEL,
            dropdown_hover_color=theme.HOVER,
            dropdown_text_color=theme.PAPER,
        )
        lang_menu.set(lang_display)
        lang_menu.pack(side="right", padx=(8, 0))
        self._entries["language"] = lang_menu

    def _on_language_change(self, value: str) -> None:
        lang = "es" if value == "Español" else "en"
        save_language(lang)

    def _build_footer(self, parent) -> None:
        self._status_label = ctk.CTkLabel(
            parent,
            text="",
            font=theme.font("small"),
            text_color=theme.MUTED,
            wraplength=540,
            anchor="w",
            justify="left",
            height=16,
        )
        self._status_label.pack(fill="x", pady=(0, 8))

        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.pack(fill="x")

        self._test_btn = ctk.CTkButton(
            buttons,
            text=t("Probar conexión"),
            command=self._on_test_connection,
            width=160,
            height=40,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.LABEL,
            corner_radius=9,
            border_width=1,
            border_color=theme.BORDER,
        )
        self._test_btn.pack(side="left")

        self._save_btn = ctk.CTkButton(
            buttons,
            text=t("Guardar cambios"),
            command=self._on_save,
            height=40,
            font=theme.font("body", "bold"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_DEEP,
            text_color=theme.ACCENT_INK,
            corner_radius=9,
            border_width=0,
        )
        self._save_btn.pack(side="right", fill="x", expand=True, padx=(12, 0))

    # ------------------------------------------------------------- behaviour --
    def _toggle_secret_visibility(self, key: str) -> None:
        entry = self._entries.get(key)
        button = self._toggle_btns.get(key)
        if not isinstance(entry, ctk.CTkEntry) or button is None:
            return
        if entry.cget("show") == "*":
            entry.configure(show="")
            button.configure(text=t("Ocultar"), text_color=theme.ACCENT)
        else:
            entry.configure(show="*")
            button.configure(text=t("Mostrar"), text_color=theme.LABEL)

    def _collect_config(self) -> tuple[dict, Optional[str]]:
        config = self._repo.load()
        for key, widget in self._entries.items():
            if key == "enable_fallback_artwork":
                config[key] = bool(widget.get() == 1)
                continue
            value = widget.get().strip()
            if key == "poll_interval":
                try:
                    interval = int(value)
                except ValueError:
                    return {}, t("El intervalo debe ser un número entero.")
                if interval < 5:
                    return {}, t("El intervalo mínimo es de 5 segundos.")
                config[key] = interval
            else:
                config[key] = value

        missing = [
            label
            for key, label in (
                ("lastfm_username", t("usuario de Last.fm")),
                ("lastfm_api_key", t("API Key")),
                ("discord_client_id", t("Discord Client ID")),
            )
            if not config.get(key)
        ]
        if missing:
            return {}, t("Faltan datos: ") + ", ".join(missing) + "."
        return config, None

    def _on_save(self) -> None:
        config, error = self._collect_config()
        if error:
            self._set_status(error, error=True)
            return

        try:
            self._repo.save(config)
        except OSError:
            logger.exception("Could not save configuration")
            self._set_status(t("No se pudo guardar la configuración."), error=True)
            return

        self._config = config
        self._saved = True
        self._set_status(t("Guardado. Aplicando cambios…"), error=False)

        if self._on_save_callback:
            try:
                self._on_save_callback()
            except Exception:
                logger.exception("The settings-saved callback failed")
                self._set_status(
                    t("Guardado, pero no se pudo reiniciar Discord."), error=True
                )
                return
            if self._root:
                self._root.after(
                    1600,
                    lambda: self._set_status(
                        t("Listo. Discord usará estos ajustes."), error=False
                    ),
                )
        else:
            if self._root:
                self._root.after(700, self._destroy_root)

    def _on_test_connection(self) -> None:
        if not self._test_btn:
            return
        self._test_btn.configure(state="disabled", text=t("Probando…"))
        self._set_status(t("Probando credenciales de Last.fm…"), error=False)

        def worker() -> None:
            username_widget = self._entries.get("lastfm_username")
            api_key_widget = self._entries.get("lastfm_api_key")
            username = (
                username_widget.get().strip()
                if isinstance(username_widget, ctk.CTkEntry)
                else ""
            )
            api_key = (
                api_key_widget.get().strip()
                if isinstance(api_key_widget, ctk.CTkEntry)
                else ""
            )

            if not username or not api_key:
                self._post(lambda: self._finish_test(t("Usuario y API Key son obligatorios."), True))
                return

            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        "https://ws.audioscrobbler.com/2.0/",
                        params={
                            "method": "user.getRecentTracks",
                            "user": username,
                            "api_key": api_key,
                            "format": "json",
                            "limit": 1,
                        },
                    )
                if response.status_code != 200:
                    self._post(
                        lambda: self._finish_test(
                            f"{t('Last.fm respondió HTTP')} {response.status_code}.", True
                        )
                    )
                    return
                payload = response.json()
                if "error" in payload:
                    message = str(payload.get("message") or t("Credenciales rechazadas."))
                    self._post(lambda: self._finish_test(f"{t('Last.fm: ')}{message}", True))
                else:
                    self._post(
                        lambda: self._finish_test(t("Conexión correcta con Last.fm."), False)
                    )
            except httpx.TimeoutException:
                self._post(lambda: self._finish_test(t("Last.fm tardó demasiado en responder."), True))
            except Exception:
                logger.exception("Connection test failed")
                self._post(lambda: self._finish_test(t("No se pudo conectar con Last.fm."), True))

        threading.Thread(target=worker, daemon=True, name="ConfigTest").start()

    def _finish_test(self, message: str, error: bool) -> None:
        self._set_status(message, error=error)
        if self._test_btn:
            self._test_btn.configure(
                state="normal",
                text=t("Probar conexión"),
            )

    def _post(self, callback) -> None:
        if not self._root:
            return
        try:
            self._root.after(0, callback)
        except Exception:
            pass

    def _set_status(self, message: str, error: bool) -> None:
        if not self._status_label:
            return
        try:
            if not self._status_label.winfo_exists():
                return
            self._status_label.configure(
                text=message,
                text_color=theme.ERROR if error else theme.ACCENT,
            )
        except Exception:
            pass

    def _on_close(self) -> None:
        self._destroy_root()


def run_config_window(on_save_callback=None, master=None) -> bool:
    window = ConfigWindow(on_save_callback, master=master)
    return window.show()
