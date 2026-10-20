"""The app's main surface: a now-playing console with per-song cover choice.

The window opens from the tray, mirrors Last.fm's current track, and lets the
user pin one of the three artwork sources for that song. Settings live behind
the gear. Closing the window hides it to the tray; the daemon keeps running.
"""

from __future__ import annotations

import asyncio
import math
import queue
import threading
import webbrowser
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote_plus

import customtkinter as ctk
import tkinter as tk
from PIL import Image

from config.logging_config import get_logger
from src.application.services.candidate_artwork_service import CandidateArtworkService
from src.domain.entities.song_override import SongOverride
from src.domain.interfaces.song_override_repository import SongOverrideRepository
from src.infrastructure.persistence.json_config_repository import JsonConfigRepository
from src.infrastructure.persistence.json_song_override_repository import JsonSongOverrideRepository
from src.infrastructure.providers.lastfm_recent_tracks import (
    LastFmFeedError,
    LastFmRecentTracksClient,
    RecentTrack,
)
from src.presentation.gui import theme

logger = get_logger(__name__)

SOURCE_LABELS = {"base": "Last.fm", "deezer": "Deezer", "musicbrainz": "MusicBrainz", "none": "Sin portada"}
SOURCE_ORDER = ("base", "deezer", "musicbrainz")
COVER_SIZE = 300
RECENT_COVER = 72
TILE_COVER = 64
DEFAULT_POLL_SECONDS = 30
MIN_POLL_SECONDS = 5
MAX_POLL_SECONDS = 300
RECENT_LIMIT = 10
SHELF_LIMIT = 6


def _poll_interval_from_config(config: dict) -> int:
    """Clamp the configured poll interval so the player can never spin free."""
    try:
        value = int(str(config.get("poll_interval") or "").strip())
    except (TypeError, ValueError):
        return DEFAULT_POLL_SECONDS
    return max(MIN_POLL_SECONDS, min(MAX_POLL_SECONDS, value))


class PlayerWindow:
    """Singleton Tk window; Tk runs in the thread that calls ``show()``."""

    _instance: "Optional[PlayerWindow]" = None
    _instance_lock = threading.Lock()
    _show_requests: "queue.Queue[bool]" = queue.Queue()
    _refresh_requests: "queue.Queue[bool]" = queue.Queue()
    _config_requests: "queue.Queue[Optional[Callable[[], None]]]" = queue.Queue()

    def __init__(
        self,
        on_open_config: Optional[Callable[[], None]] = None,
        fetcher: Optional[Callable[[str, str, int], list[RecentTrack]]] = None,
        overrides: Optional[SongOverrideRepository] = None,
        on_config_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_open_config = on_open_config
        self._on_config_saved = on_config_saved
        self._fetcher = fetcher or LastFmRecentTracksClient().fetch
        self._config_repo = JsonConfigRepository()
        self._overrides = overrides or JsonSongOverrideRepository()

        self._root: Optional[ctk.CTk] = None
        self._tracks: list[RecentTrack] = []
        self._selected: Optional[RecentTrack] = None
        self._current_key: Optional[str] = None
        self._follow_current = True
        self._recent_pil: dict[str, Optional[Image.Image]] = {}

        self._candidate_key: Optional[str] = None
        self._candidates: dict[str, Optional[str]] = {}
        self._candidate_images: dict[str, Optional[Image.Image]] = {}
        self._candidate_cache: dict[str, tuple[dict[str, Optional[str]], dict[str, Optional[Image.Image]]]] = {}
        self._choice: Optional[str] = None
        self._override: Optional[SongOverride] = None

        self._loading = False
        self._visible = False
        self._last_updated: Optional[datetime] = None
        self._poll_seconds = DEFAULT_POLL_SECONDS
        self._poll_job: Optional[str] = None
        self._eq_job: Optional[str] = None
        self._eq_phase = 0.0
        self._eq_active = False
        self._manager: Optional["OverrideManager"] = None
        self._cover_ctk: Optional[ctk.CTkImage] = None
        self._open_accent = False

    # ------------------------------------------------------------ lifecycle --
    @classmethod
    def request_show(cls) -> bool:
        """Ask an existing window to come forward. Returns True if it exists."""
        cls._show_requests.put(True)
        return cls._instance is not None

    @classmethod
    def request_refresh(cls) -> None:
        cls._refresh_requests.put(True)

    @classmethod
    def request_open_config(cls, on_config_saved: Optional[Callable[[], None]] = None) -> bool:
        """Ask an existing player window to open Ajustes in its own Tk loop."""
        cls._config_requests.put(on_config_saved)
        return cls._instance is not None

    def show(self) -> None:
        with PlayerWindow._instance_lock:
            if PlayerWindow._instance is not None:
                PlayerWindow.request_show()
                return
            PlayerWindow._instance = self

        try:
            self._root = ctk.CTk()
            self._root.title("LastfmPresence")
            self._root.configure(fg_color=theme.INK)
            self._root.geometry("920x700")
            self._root.resizable(False, False)
            theme.set_window_icon(self._root)

            self._build_ui()
            self._center_window()

            self._root.protocol("WM_DELETE_WINDOW", self._hide)
            self._root.bind("<Escape>", lambda _event: self._hide())
            self._root.after(120, self._drain_queues)
            self._root.after(250, self._initial_load)

            self._visible = True
            self._root.deiconify()
            self._root.mainloop()
        except Exception:
            logger.exception("Player window crashed")
        finally:
            self._stop_eq()
            with PlayerWindow._instance_lock:
                if PlayerWindow._instance is self:
                    PlayerWindow._instance = None

    def _center_window(self) -> None:
        if not self._root:
            return
        try:
            self._root.update_idletasks()
            width, height = 920, 700
            scale = ctk.ScalingTracker.get_window_scaling(self._root)
            screen_width = int(self._root.winfo_screenwidth() * scale)
            screen_height = int(self._root.winfo_screenheight() * scale)
            physical_width = int(width * scale)
            physical_height = int(height * scale)
            x = max(0, (screen_width - physical_width) // 2)
            y = max(0, (screen_height - physical_height) // 2 - 20)
            self._root.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def _initial_load(self) -> None:
        self._refresh()
        self._schedule_poll()

    def _hide(self) -> None:
        if not self._root:
            return
        self._visible = False
        self._stop_eq()
        try:
            self._root.withdraw()
        except Exception:
            pass

    def _show_window(self) -> None:
        if not self._root:
            return
        try:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
            self._root.attributes("-topmost", True)
            self._root.after(120, lambda: self._root.attributes("-topmost", False) if self._root else None)
        except Exception as e:
            logger.warning(f"Could not show player window: {e}")
        self._visible = True
        self._follow_current = True
        self._refresh()

    def _drain_queues(self) -> None:
        if not self._root:
            return
        show = False
        while True:
            try:
                PlayerWindow._show_requests.get_nowait()
            except queue.Empty:
                break
            show = True
        if show:
            self._show_window()

        refresh = False
        while True:
            try:
                PlayerWindow._refresh_requests.get_nowait()
            except queue.Empty:
                break
            refresh = True
        if refresh:
            self._refresh()

        while True:
            try:
                callback = PlayerWindow._config_requests.get_nowait()
            except queue.Empty:
                break
            self._open_config(callback)

        try:
            self._root.after(120, self._drain_queues)
        except Exception:
            pass

    def _schedule_poll(self) -> None:
        if not self._root:
            return
        if self._poll_job is not None:
            try:
                self._root.after_cancel(self._poll_job)
            except Exception:
                pass
        self._poll_job = self._root.after(self._poll_seconds * 1000, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._poll_job = None
        if self._visible:
            self._refresh()
        self._update_footer()
        self._schedule_poll()

    # ----------------------------------------------------------------- UI ----
    def _icon_button(
        self,
        parent,
        name: str,
        command: Callable[[], None],
        size: int = 18,
        color: str = theme.LABEL,
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text="",
            image=theme.icon(name, size, color),
            command=command,
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=theme.HOVER,
            corner_radius=9,
            border_width=0,
        )

    def _build_ui(self) -> None:
        assert self._root is not None
        root = self._root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        self._build_header(root)

        hairline = ctk.CTkFrame(root, height=1, fg_color=theme.BORDER, corner_radius=0)
        hairline.grid(row=1, column=0, sticky="ew")

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=32, pady=(18, 8))
        body.grid_columnconfigure(0, weight=1)
        self._build_main(body)
        self._build_recent(body)

        footer_line = ctk.CTkFrame(root, height=1, fg_color=theme.BORDER, corner_radius=0)
        footer_line.grid(row=3, column=0, sticky="ew")
        self._build_footer(root)

    def _build_header(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color=theme.INK, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="ew")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28)

        logo_pil = theme.app_icon_pil(26)
        if logo_pil is not None:
            ctk.CTkLabel(
                inner,
                text="",
                image=theme.pil_to_ctk(logo_pil, (26, 26)),
            ).pack(side="left", padx=(0, 11))

        ctk.CTkLabel(
            inner,
            text="LastfmPresence",
            font=theme.font("display", "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
        ).pack(side="left")

        self._icon_button(inner, "gear", self._open_config, size=19, color=theme.LABEL).pack(
            side="right", padx=(8, 0)
        )
        self._icon_button(inner, "refresh", self._refresh, size=18, color=theme.MUTED).pack(
            side="right"
        )

    def _build_main(self, parent) -> None:
        assert self._root is not None
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid(row=0, column=0, sticky="nsew")
        main.grid_columnconfigure(1, weight=1)
        self._main = main

        self._cover_ctk = theme.placeholder_image(COVER_SIZE, 12)
        self._cover_label = ctk.CTkLabel(main, text="", image=self._cover_ctk)
        self._cover_label.grid(row=0, column=0, sticky="nw")

        info = ctk.CTkFrame(main, fg_color="transparent")
        info.grid(row=0, column=1, sticky="nsew", padx=(38, 0))
        self._info = info

        self._build_track_info(info)
        self._build_cover_picker(info)

    def _build_track_info(self, parent) -> None:
        status_row = ctk.CTkFrame(parent, fg_color="transparent")
        status_row.pack(fill="x", anchor="w")

        self._status_dot = ctk.CTkFrame(
            status_row,
            width=7,
            height=7,
            corner_radius=4,
            fg_color=theme.MUTED,
        )
        self._status_dot.pack(side="left", padx=(0, 8))

        self._status_label = ctk.CTkLabel(
            status_row,
            text="CONECTANDO",
            font=theme.font("tiny", "bold"),
            text_color=theme.MUTED,
            anchor="w",
            height=14,
        )
        self._status_label.pack(side="left")

        self._title_label = ctk.CTkLabel(
            parent,
            text="Buscando tu última reproducción…",
            font=theme.font(30, "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self._title_label.pack(fill="x", pady=(7, 2))

        self._artist_label = ctk.CTkLabel(
            parent,
            text="",
            font=theme.font("display"),
            text_color=theme.LABEL,
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self._artist_label.pack(fill="x")

        self._album_label = ctk.CTkLabel(
            parent,
            text=" ",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
            justify="left",
            wraplength=480,
            height=16,
        )
        self._album_label.pack(fill="x", pady=(2, 0))

        eq_row = ctk.CTkFrame(parent, fg_color="transparent")
        eq_row.pack(fill="x", pady=(10, 0))

        self._eq = tk.Canvas(
            eq_row,
            width=92,
            height=30,
            bg=theme.INK,
            highlightthickness=0,
            bd=0,
        )
        self._eq.pack(side="left")
        self._draw_eq(False)

        self._open_btn = ctk.CTkButton(
            eq_row,
            text="Abrir en Last.fm",
            image=theme.icon("external", 13, theme.MUTED),
            compound="left",
            command=self._open_lastfm,
            height=28,
            width=142,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.LABEL,
            corner_radius=7,
        )
        self._open_btn.pack(side="right")

    def _build_cover_picker(self, parent) -> None:
        self._cover_separator = ctk.CTkFrame(
            parent, height=1, fg_color=theme.BORDER, corner_radius=0
        )
        self._cover_separator.pack(fill="x", pady=(14, 12))

        self._cover_section = ctk.CTkFrame(parent, fg_color="transparent")
        self._cover_section.pack(fill="x")

        heading = ctk.CTkFrame(self._cover_section, fg_color="transparent")
        heading.pack(fill="x")

        ctk.CTkLabel(
            heading,
            text="Carátula",
            font=theme.font("small", "bold"),
            text_color=theme.LABEL,
            anchor="w",
            height=16,
        ).pack(side="left")

        self._cover_state = ctk.CTkLabel(
            heading,
            text="Automática",
            font=theme.font("tiny"),
            text_color=theme.MUTED,
            anchor="e",
            height=16,
        )
        self._cover_state.pack(side="right")

        self._tiles_host = ctk.CTkFrame(self._cover_section, fg_color="transparent")
        self._tiles_host.pack(fill="x", pady=(8, 0))

        actions = ctk.CTkFrame(self._cover_section, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))

        self._save_btn = ctk.CTkButton(
            actions,
            text="Guardar carátula",
            command=self._save_override,
            width=148,
            height=34,
            font=theme.font("body", "bold"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_DEEP,
            text_color=theme.ACCENT_INK,
            corner_radius=8,
            border_width=0,
        )
        self._save_btn.pack(side="left")

        self._remove_btn = ctk.CTkButton(
            actions,
            text="Quitar",
            image=theme.icon("close", 11, theme.LABEL),
            compound="left",
            command=self._remove_override,
            width=82,
            height=34,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.LABEL,
            corner_radius=8,
            border_width=0,
        )

        self._save_note = ctk.CTkLabel(
            self._cover_section,
            text="",
            font=theme.font("tiny"),
            text_color=theme.MUTED,
            anchor="w",
            justify="left",
            wraplength=480,
            height=14,
        )
        self._save_note.pack(fill="x", pady=(7, 0))

        self._cover_section.pack_forget()

    def _build_recent(self, parent) -> None:
        divider = ctk.CTkFrame(parent, height=1, fg_color=theme.BORDER, corner_radius=0)
        divider.grid(row=1, column=0, sticky="ew", pady=(14, 12))

        recent = ctk.CTkFrame(parent, fg_color="transparent")
        recent.grid(row=2, column=0, sticky="ew")
        self._recent_section = recent

        header = ctk.CTkFrame(recent, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="Recientes",
            font=theme.font("display", "bold", display=True),
            text_color=theme.LABEL,
            anchor="w",
            height=16,
        ).pack(side="left")

        self._follow_btn = ctk.CTkButton(
            header,
            text="Volver a la actual",
            command=self._return_to_current,
            height=24,
            width=128,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.ACCENT,
            corner_radius=6,
            border_width=0,
        )

        self._shelf = ctk.CTkFrame(recent, fg_color="transparent")
        self._shelf.pack(fill="x", pady=(8, 0))
        for column in range(SHELF_LIMIT):
            self._shelf.grid_columnconfigure(column, weight=1)

        self._shelf_time_font = theme.font("tiny")
        self._shelf_title_font = theme.font("small")
        self._shelf_artist_font = theme.font("tiny")
        self._tile_font = theme.font("tiny")
        self._render_recent()

    def _build_footer(self, parent) -> None:
        footer = ctk.CTkFrame(parent, fg_color=theme.INK, corner_radius=0, height=44)
        footer.grid(row=4, column=0, sticky="ew")
        footer.pack_propagate(False)

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32)

        ctk.CTkLabel(
            inner,
            text="Datos de Last.fm",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
        ).pack(side="left")

        self._updated_label = ctk.CTkLabel(
            inner,
            text="",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="e",
        )
        self._updated_label.pack(side="right")

        self._overrides_btn = ctk.CTkButton(
            inner,
            text="Sin carátulas personalizadas",
            command=self._open_manager,
            height=24,
            width=200,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.MUTED,
            corner_radius=6,
            border_width=0,
            state="disabled",
        )
        self._overrides_btn.pack(side="right", padx=(0, 20))

    # --------------------------------------------------------------- data ----
    def _refresh(self) -> None:
        if not self._root or self._loading:
            return

        config = self._config_repo.load()
        self._poll_seconds = _poll_interval_from_config(config)
        username = str(config.get("lastfm_username") or "").strip()
        api_key = str(config.get("lastfm_api_key") or "").strip()

        if not username or not api_key:
            self._render_unconfigured()
            return

        self._loading = True
        if self._selected is None:
            self._render_loading()
        else:
            self._updated_label.configure(text="Actualizando…")

        threading.Thread(
            target=self._fetch_worker,
            args=(username, api_key),
            daemon=True,
            name="PlayerFeed",
        ).start()

    def _fetch_worker(self, username: str, api_key: str) -> None:
        try:
            tracks = self._fetcher(username, api_key, RECENT_LIMIT)
        except LastFmFeedError as exc:
            message = str(exc)
            self._post(lambda: self._finish_error(message))
            return
        except Exception:
            logger.exception("Could not read the Last.fm recent-tracks feed")
            self._post(lambda: self._finish_error("No se pudo conectar con Last.fm."))
            return

        covers: dict[str, Optional[Image.Image]] = {}
        seen: set[str] = set()
        for track in tracks:
            if track.key in seen:
                continue
            seen.add(track.key)
            try:
                override = self._overrides.get(track.artist, track.title)
            except Exception:
                override = None
            source_url = override.url if override is not None else track.artwork_url
            image = theme.load_pil_image(source_url) if source_url else None
            if image is not None or track.key not in covers:
                covers[track.key] = image
            if len(seen) >= SHELF_LIMIT:
                break

        self._post(lambda: self._finish_load(tracks, covers))

    def _finish_load(
        self, tracks: list[RecentTrack], covers: dict[str, Optional[Image.Image]]
    ) -> None:
        self._loading = False
        self._last_updated = datetime.now(timezone.utc)
        self._apply_tracks(tracks, covers)
        self._update_footer()

    def _finish_error(self, message: str) -> None:
        self._loading = False
        self._render_error(message)

    def _apply_tracks(
        self, tracks: list[RecentTrack], covers: dict[str, Optional[Image.Image]]
    ) -> None:
        self._tracks = tracks
        self._recent_pil.update(covers)

        if not tracks:
            self._current_key = None
            self._selected = None
            self._render_empty()
            self._render_recent()
            return

        current = next((track for track in tracks if track.now_playing), tracks[0])
        self._current_key = current.key

        if self._follow_current or self._selected is None:
            self._select_track(current, follow=True)
            return

        fresh = next((track for track in tracks if track.key == self._selected.key), None)
        if fresh is not None:
            artwork_changed = fresh.artwork_url != self._selected.artwork_url
            self._selected = fresh
            if artwork_changed:
                self._recent_pil.pop(fresh.key, None)
            self._render_details()
        self._render_recent()
        self._update_follow_button()
        self._update_footer()

    def _select_track(self, track: RecentTrack, follow: bool = True) -> None:
        same_track = self._selected is not None and self._selected.key == track.key
        self._selected = track
        self._follow_current = follow
        self._override = self._overrides.get(track.artist, track.title)

        if not same_track:
            self._choice = None
            self._candidates = {}
            self._candidate_images = {}
            self._candidate_key = None
            self._clear_note()
            self._set_cover(self._recent_pil.get(track.key))
            self._load_candidates(track)
        else:
            self._set_cover(self._current_cover_pil())

        self._show_cover_section()
        self._render_details()
        self._render_recent()
        self._update_follow_button()
        self._update_footer()

    def _shelf_tracks(self) -> list[RecentTrack]:
        unique: list[RecentTrack] = []
        seen: set[str] = set()
        for track in self._tracks:
            if track.key in seen:
                continue
            seen.add(track.key)
            unique.append(track)
            if len(unique) >= SHELF_LIMIT:
                break
        return unique

    def _on_recent_click(self, track: RecentTrack) -> None:
        self._select_track(track, follow=track.key == self._current_key)

    def _return_to_current(self) -> None:
        current = next((track for track in self._tracks if track.key == self._current_key), None)
        if current is not None:
            self._select_track(current, follow=True)

    def _update_follow_button(self) -> None:
        selected_is_current = (
            self._selected is not None and self._selected.key == self._current_key
        )
        if self._follow_current or self._current_key is None or selected_is_current:
            self._follow_btn.pack_forget()
        elif not self._follow_btn.winfo_manager():
            self._follow_btn.pack(side="right")

    # ------------------------------------------------------------ rendering --
    def _render_details(self) -> None:
        track = self._selected
        if track is None:
            return

        is_current = track.key == self._current_key
        if track.now_playing and is_current:
            self._set_status("AHORA SUENA", theme.ACCENT)
        elif is_current:
            relative = theme.format_relative_time(track.played_at)
            suffix = f" · {relative}" if relative else ""
            self._set_status(f"ÚLTIMA REPRODUCCIÓN{suffix}", theme.MUTED)
        else:
            relative = theme.format_relative_time(track.played_at)
            suffix = f" · {relative}" if relative else ""
            self._set_status(f"VISTA PREVIA{suffix}", theme.MUTED)

        self._title_label.configure(text=track.title)
        self._artist_label.configure(text=track.artist)
        self._album_label.configure(text=track.album or " ")
        self._set_open_action("Abrir en Last.fm", self._open_lastfm, icon="external")

        if track.now_playing and self._follow_current:
            self._start_eq()
        else:
            self._stop_eq()

    def _render_recent(self) -> None:
        if not hasattr(self, "_shelf"):
            return
        for child in self._shelf.winfo_children():
            child.destroy()

        if not self._tracks:
            ctk.CTkLabel(
                self._shelf,
                text="Aún no hay reproducciones.",
                font=theme.font("small"),
                text_color=theme.MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=(2, 0), pady=(2, 0))
            return

        for index, track in enumerate(self._shelf_tracks()):
            selected = self._selected is not None and track.key == self._selected.key
            tile = ctk.CTkFrame(
                self._shelf,
                fg_color=theme.HOVER if selected else "transparent",
                corner_radius=10,
                border_width=1,
                border_color=theme.ACCENT if selected else theme.INK,
            )
            tile.grid(row=0, column=index, sticky="nw", padx=(0, 10))

            cover_pil = self._shelf_cover_pil(track)
            cover = theme.pil_to_ctk(
                theme.square_cover(cover_pil, RECENT_COVER, 8),
                (RECENT_COVER, RECENT_COVER),
            )
            cover_label = ctk.CTkLabel(tile, text="", image=cover)
            cover_label.pack(anchor="w", padx=6, pady=(6, 0))

            moment = "Ahora" if track.now_playing else theme.format_relative_time(track.played_at)
            time_label = ctk.CTkLabel(
                tile,
                text=moment,
                font=self._shelf_time_font,
                text_color=theme.ACCENT if track.now_playing else theme.MUTED,
                anchor="w",
                height=14,
            )
            time_label.pack(fill="x", padx=7, pady=(6, 0))

            title_label = ctk.CTkLabel(
                tile,
                text=track.title,
                font=self._shelf_title_font,
                text_color=theme.PAPER,
                anchor="w",
                justify="left",
                wraplength=115,
                height=42,
            )
            title_label.pack(fill="x", padx=7)

            artist_label = ctk.CTkLabel(
                tile,
                text=track.artist,
                font=self._shelf_artist_font,
                text_color=theme.MUTED,
                anchor="w",
                justify="left",
                wraplength=115,
                height=22,
            )
            artist_label.pack(fill="x", padx=7, pady=(0, 6))

            for widget in (tile, cover_label, time_label, title_label, artist_label):
                widget.bind("<Button-1>", lambda _event, t=track: self._on_recent_click(t))
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass

    def _shelf_cover_pil(self, track: RecentTrack) -> Optional[Image.Image]:
        if (
            self._selected is not None
            and track.key == self._selected.key
            and self._choice
        ):
            if self._choice == "none":
                return theme.app_icon_pil(RECENT_COVER)
            image = self._candidate_images.get(self._choice)
            if image is not None:
                return image
        return self._recent_pil.get(track.key)

    def _current_cover_pil(self) -> Optional[Image.Image]:
        if self._choice:
            if self._choice == "none":
                return theme.app_icon_pil(COVER_SIZE)
            image = self._candidate_images.get(self._choice)
            if image is not None:
                return image
        if self._selected is not None:
            return self._recent_pil.get(self._selected.key)
        return None

    def _set_cover(self, image: Optional[Image.Image]) -> None:
        if not hasattr(self, "_cover_label"):
            return
        rounded = theme.square_cover(image, COVER_SIZE, 12)
        self._cover_ctk = theme.pil_to_ctk(rounded, (COVER_SIZE, COVER_SIZE))
        self._cover_label.configure(image=self._cover_ctk)

    def _show_cover_section(self) -> None:
        if not self._cover_section.winfo_manager():
            self._cover_separator.pack(fill="x", pady=(14, 12))
            self._cover_section.pack(fill="x")

    def _hide_cover_section(self) -> None:
        self._cover_separator.pack_forget()
        self._cover_section.pack_forget()

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.configure(text=text, text_color=color)
        self._status_dot.configure(fg_color=color)

    def _set_open_action(
        self,
        text: Optional[str],
        command: Optional[Callable[[], None]] = None,
        accent: bool = False,
        icon: str = "external",
    ) -> None:
        if text is None:
            self._open_btn.pack_forget()
            return
        self._open_accent = accent
        self._open_btn.configure(
            text=text,
            command=command,
            fg_color=theme.ACCENT if accent else "transparent",
            hover_color=theme.ACCENT_DEEP if accent else theme.HOVER,
            text_color=theme.ACCENT_INK if accent else theme.LABEL,
            image=theme.icon(icon, 13, theme.ACCENT_INK if accent else theme.MUTED),
            width=150 if accent else 142,
        )
        if not self._open_btn.winfo_manager():
            self._open_btn.pack(side="right")

    def _clear_note(self) -> None:
        self._save_note.configure(text="", text_color=theme.MUTED)

    def _note(self, text: str, error: bool = False) -> None:
        self._save_note.configure(
            text=text,
            text_color=theme.ERROR if error else theme.MUTED,
        )

    def _update_footer(self) -> None:
        if not hasattr(self, "_updated_label"):
            return
        if self._loading:
            self._updated_label.configure(text="Actualizando…")
        elif self._last_updated is not None:
            relative = theme.format_relative_time(int(self._last_updated.timestamp()))
            self._updated_label.configure(text=f"Actualizado {relative}")
        else:
            self._updated_label.configure(text="")

        try:
            count = len(self._overrides.all())
        except Exception:
            count = 0

        if count:
            label = (
                "1 carátula personalizada"
                if count == 1
                else f"{count} carátulas personalizadas"
            )
            self._overrides_btn.configure(text=label, state="normal", text_color=theme.ACCENT)
        else:
            self._overrides_btn.configure(
                text="Sin carátulas personalizadas",
                state="disabled",
                text_color=theme.MUTED,
            )

    # --------------------------------------------------------------- states --
    def _render_loading(self) -> None:
        self._tracks = []
        self._selected = None
        self._current_key = None
        self._set_cover(None)
        self._set_status("CONECTANDO", theme.MUTED)
        self._title_label.configure(text="Buscando tu última reproducción…")
        self._artist_label.configure(text="Leyendo tu actividad de Last.fm.")
        self._album_label.configure(text=" ")
        self._hide_cover_section()
        self._set_open_action(None)
        self._stop_eq()
        self._render_recent()
        self._follow_btn.pack_forget()
        self._updated_label.configure(text="Actualizando…")

    def _render_unconfigured(self) -> None:
        self._tracks = []
        self._selected = None
        self._current_key = None
        self._set_cover(None)
        self._set_status("SIN CONFIGURAR", theme.MUTED)
        self._title_label.configure(text="Conecta tu cuenta")
        self._artist_label.configure(
            text="Añade tus credenciales de Last.fm y Discord para empezar."
        )
        self._album_label.configure(text=" ")
        self._hide_cover_section()
        self._set_open_action("Abrir ajustes", self._open_config, accent=True, icon="gear")
        self._stop_eq()
        self._render_recent()
        self._follow_btn.pack_forget()
        self._updated_label.configure(text="Sin datos")

    def _render_empty(self) -> None:
        self._set_cover(None)
        self._set_status("EN ESPERA", theme.MUTED)
        self._title_label.configure(text="Sin reproducción")
        self._artist_label.configure(
            text="Cuando empieces a escuchar algo, aparecerá aquí."
        )
        self._album_label.configure(text=" ")
        self._hide_cover_section()
        self._set_open_action("Actualizar", self._refresh, icon="refresh")
        self._stop_eq()
        self._follow_btn.pack_forget()

    def _render_error(self, message: str) -> None:
        if self._selected is not None:
            self._note("No se pudo actualizar. Se muestra la última lectura.", error=True)
            self._updated_label.configure(text="No se pudo actualizar")
            return

        self._tracks = []
        self._selected = None
        self._current_key = None
        self._set_cover(None)
        self._set_status("SIN CONEXIÓN", theme.ERROR)
        self._title_label.configure(text="No se pudo leer Last.fm")
        self._artist_label.configure(text=message)
        self._album_label.configure(text=" ")
        self._hide_cover_section()
        self._set_open_action("Reintentar", self._refresh, icon="refresh")
        self._stop_eq()
        self._render_recent()
        self._follow_btn.pack_forget()
        self._updated_label.configure(text="Sin conexión")

    # ------------------------------------------------------------ candidates --
    def _load_candidates(self, track: RecentTrack) -> None:
        cache_key = f"{track.key}|{track.artwork_url}"
        self._candidate_key = cache_key

        cached = self._candidate_cache.get(cache_key)
        if cached is not None:
            self._candidates, self._candidate_images = cached
            self._choose_default_source()
            self._render_tiles()
            self._set_cover(self._current_cover_pil())
            self._update_save_state()
            return

        self._show_candidates_loading()
        self._update_save_state()

        def worker() -> None:
            async def resolve() -> dict[str, Optional[str]]:
                service = CandidateArtworkService()
                try:
                    return await service.get_candidates(
                        track.artist,
                        track.title,
                        track.album,
                        track.artwork_url,
                    )
                finally:
                    await service.close()

            try:
                urls = asyncio.run(resolve())
            except Exception:
                logger.exception("Could not resolve artwork candidates")
                self._post(lambda: self._finish_candidates_error(cache_key))
                return

            images: dict[str, Optional[Image.Image]] = {}
            for source, url in urls.items():
                if url:
                    images[source] = theme.load_pil_image(url)
            self._post(lambda: self._finish_candidates(cache_key, urls, images))

        threading.Thread(
            target=worker,
            daemon=True,
            name="PlayerCandidates",
        ).start()

    def _show_candidates_loading(self) -> None:
        for child in self._tiles_host.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self._tiles_host,
            text="Buscando carátulas en Deezer y MusicBrainz…",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 6))
        self._note("Consultando fuentes alternativas.")

    def _finish_candidates(
        self,
        cache_key: str,
        urls: dict[str, Optional[str]],
        images: dict[str, Optional[Image.Image]],
    ) -> None:
        if cache_key != self._candidate_key:
            return
        self._candidates = urls
        self._candidate_images = images
        if any(urls.values()):
            self._candidate_cache[cache_key] = (urls, images)
        self._choose_default_source()
        self._render_tiles()
        self._set_cover(self._current_cover_pil())
        self._render_recent()
        self._update_save_state()
        if not any(urls.values()):
            self._note("No se encontraron carátulas alternativas.")
        else:
            self._clear_note()

    def _finish_candidates_error(self, cache_key: str) -> None:
        if cache_key != self._candidate_key:
            return
        self._candidates = {"base": None, "deezer": None, "musicbrainz": None}
        self._candidate_images = {}
        self._choice = None
        self._render_tiles()
        self._update_save_state()
        self._note("No se pudieron consultar las fuentes alternativas.", error=True)

    def _choose_default_source(self) -> None:
        available = [source for source in SOURCE_ORDER if self._candidates.get(source)]
        if self._choice in available:
            return
        if self._override is not None and self._override.source in available:
            self._choice = self._override.source
            return
        if self._override is not None and self._override.source == "none":
            self._choice = "none"
            return
        self._choice = available[0] if available else None

    # ---------------------------------------------------------------- tiles --
    def _render_tiles(self) -> None:
        for child in self._tiles_host.winfo_children():
            child.destroy()

        # Siempre se ofrece la opción de no usar portada (se muestra el logo de la app)
        sources = list(SOURCE_ORDER) + ["none"]

        for source in sources:
            if source == "none":
                enabled = True
                url = None
                selected = self._choice == "none"
            else:
                url = self._candidates.get(source)
                enabled = bool(url)
                selected = enabled and self._choice == source

            tile = ctk.CTkFrame(
                self._tiles_host,
                fg_color=theme.HOVER if selected else (theme.PANEL if enabled else theme.INK),
                corner_radius=9,
                border_width=2 if selected else 1,
                border_color=theme.ACCENT if selected else theme.BORDER,
            )
            tile.pack(side="left", padx=(0, 10))

            cover = None
            if source == "none":
                logo_pil = theme.app_icon_pil(TILE_COVER)
                if logo_pil is not None:
                    image = theme.pil_to_ctk(
                        theme.square_cover(logo_pil, TILE_COVER, 7),
                        (TILE_COVER, TILE_COVER),
                    )
                    cover = ctk.CTkLabel(tile, text="", image=image)
                    cover.pack(padx=4, pady=(4, 0))
                else:
                    empty = ctk.CTkFrame(
                        tile,
                        width=TILE_COVER,
                        height=TILE_COVER,
                        fg_color=theme.INK,
                        corner_radius=6,
                    )
                    empty.pack(padx=4, pady=(4, 0))
                    empty.pack_propagate(False)
                    ctk.CTkLabel(
                        empty,
                        text="Sin\nportada",
                        font=theme.font("tiny"),
                        text_color=theme.MUTED,
                        justify="center",
                    ).pack(expand=True)
            elif enabled:
                image = theme.pil_to_ctk(
                    theme.square_cover(self._candidate_images.get(source), TILE_COVER, 7),
                    (TILE_COVER, TILE_COVER),
                )
                cover = ctk.CTkLabel(tile, text="", image=image)
                cover.pack(padx=4, pady=(4, 0))
            else:
                empty = ctk.CTkFrame(
                    tile,
                    width=TILE_COVER,
                    height=TILE_COVER,
                    fg_color=theme.INK,
                    corner_radius=6,
                )
                empty.pack(padx=4, pady=(4, 0))
                empty.pack_propagate(False)
                ctk.CTkLabel(
                    empty,
                    text="Sin\nportada",
                    font=theme.font("tiny"),
                    text_color=theme.MUTED,
                    justify="center",
                ).pack(expand=True)

            label_row = ctk.CTkFrame(tile, fg_color="transparent")
            label_row.pack(fill="x", padx=5, pady=(4, 5))

            if source == "none":
                text_color = theme.ACCENT if selected else theme.LABEL
            else:
                text_color = theme.ACCENT if selected else (theme.LABEL if enabled else theme.MUTED)

            label = ctk.CTkLabel(
                label_row,
                text=SOURCE_LABELS[source],
                font=self._tile_font,
                text_color=text_color,
                anchor="w",
                height=14,
            )
            label.pack(side="left")

            widgets = [tile, label_row, label]
            if cover is not None:
                widgets.append(cover)
                if selected:
                    check = ctk.CTkLabel(
                        label_row,
                        text="",
                        image=theme.icon("check", 9, theme.ACCENT),
                        height=14,
                    )
                    check.pack(side="right")
                    widgets.append(check)

            for widget in widgets:
                widget.bind(
                    "<Button-1>",
                    lambda _event, s=source: self._select_source(s),
                )
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass

    def _select_source(self, source: str) -> None:
        if source != "none" and not self._candidates.get(source):
            return
        self._choice = source
        self._render_tiles()
        self._set_cover(self._current_cover_pil())
        self._render_recent()
        self._update_save_state()
        self._clear_note()

    def _update_save_state(self) -> None:
        url = None if self._choice == "none" else self._candidates.get(self._choice)
        override = self._override
        saved = bool(
            override is not None
            and override.source == self._choice
            and override.url == url
        )

        if saved:
            self._save_btn.configure(
                text="Guardada",
                state="disabled",
                fg_color=theme.ELEVATED,
                text_color=theme.ACCENT,
            )
        elif self._choice == "none" or url:
            self._save_btn.configure(
                text="Guardar carátula",
                state="normal",
                fg_color=theme.ACCENT,
                hover_color=theme.ACCENT_DEEP,
                text_color=theme.ACCENT_INK,
            )
        else:
            self._save_btn.configure(
                text="Guardar carátula",
                state="disabled",
                fg_color=theme.PANEL,
                text_color=theme.MUTED,
            )

        if override is not None:
            if not self._remove_btn.winfo_manager():
                self._remove_btn.pack(side="left", padx=(10, 0))
            self._cover_state.configure(text="Personalizada", text_color=theme.ACCENT)
        else:
            self._remove_btn.pack_forget()
            self._cover_state.configure(text="Automática", text_color=theme.MUTED)

    def _save_override(self) -> None:
        track = self._selected
        if track is None or not self._choice:
            return
        url = None if self._choice == "none" else self._candidates.get(self._choice)
        if self._choice != "none" and not url:
            return

        try:
            override = SongOverride(
                artist=track.artist,
                title=track.title,
                source=self._choice,
                url=url,
            )
            self._overrides.save(override)
        except Exception:
            logger.exception("Could not save artwork override")
            self._note("No se pudo guardar la carátula.", error=True)
            return

        self._override = override
        self._render_tiles()
        self._set_cover(self._current_cover_pil())
        self._render_recent()
        self._update_save_state()
        if self._choice == "none":
            self._note("Sin portada. Se usará el logo de la app.")
        else:
            self._note("Guardada. Discord la usará cuando cambie la pista.")
        self._update_footer()

    def _remove_override(self) -> None:
        track = self._selected
        if track is None:
            return
        try:
            removed = self._overrides.remove(track.artist, track.title)
        except Exception:
            logger.exception("Could not remove artwork override")
            self._note("No se pudo quitar la personalización.", error=True)
            return

        self._override = None
        self._choice = None
        self._choose_default_source()
        self._render_tiles()
        self._set_cover(self._current_cover_pil())
        self._render_recent()
        self._update_save_state()
        if removed:
            self._note("Personalización eliminada. Se usará la carátula automática.")
        else:
            self._note("Esta canción no tenía una carátula personalizada.")
        self._update_footer()

    # -------------------------------------------------------------- actions --
    def _open_config(self, on_config_saved: Optional[Callable[[], None]] = None) -> None:
        """Open Ajustes inside this window's Tk loop when a save callback exists."""
        callback = on_config_saved or self._on_config_saved
        if callback is not None:
            from src.presentation.gui.main_window import run_config_window

            try:
                run_config_window(on_save_callback=callback, master=self._root)
            except Exception:
                logger.exception("Could not open the settings window from the player")
            return
        if self._on_open_config is None:
            logger.info("No settings opener is wired to the player")
            return
        try:
            self._on_open_config()
        except Exception:
            logger.exception("Could not open the settings window")

    def _open_lastfm(self) -> None:
        track = self._selected
        if track is None:
            return
        artist = quote_plus(track.artist)
        title = quote_plus(track.title)
        if title:
            webbrowser.open(f"https://www.last.fm/music/{artist}/_/{title}")
        else:
            webbrowser.open(f"https://www.last.fm/music/{artist}")

    def _open_manager(self) -> None:
        if self._manager is not None:
            try:
                if self._manager.winfo_exists():
                    self._manager.lift()
                    self._manager.focus_force()
                    return
            except Exception:
                pass
        if self._root is None:
            return
        self._manager = OverrideManager(self._root, self._overrides, self._on_overrides_changed)

    def _on_overrides_changed(self) -> None:
        if self._selected is not None:
            previously = self._override
            self._override = self._overrides.get(self._selected.artist, self._selected.title)
            if previously is not None and self._override is None:
                self._choice = None
                self._choose_default_source()
                self._note("Personalización eliminada. Se usará la carátula automática.")
            self._render_tiles()
            self._set_cover(self._current_cover_pil())
            self._render_recent()
            self._update_save_state()
        self._update_footer()

    # ------------------------------------------------------------ equalizer --
    def _draw_eq(self, active: bool) -> None:
        if not hasattr(self, "_eq"):
            return
        self._eq.delete("all")
        baseline = 28
        bar_width = 4
        gap = 8
        start = 10
        for index in range(6):
            x = start + index * (bar_width + gap)
            if active:
                height = 4 + int((math.sin(self._eq_phase + index * 1.15) + 1) * 8)
            else:
                height = 2
            color = theme.ACCENT if active else theme.BORDER_STRONG
            self._eq.create_rectangle(
                x,
                baseline - height,
                x + bar_width,
                baseline,
                fill=color,
                outline="",
            )

    def _start_eq(self) -> None:
        if self._eq_job is not None:
            return
        self._eq_active = True
        self._eq_phase = 0.0
        self._animate_eq()

    def _stop_eq(self) -> None:
        if self._eq_job is not None and self._root is not None:
            try:
                self._root.after_cancel(self._eq_job)
            except Exception:
                pass
        self._eq_job = None
        self._eq_active = False
        self._draw_eq(False)

    def _animate_eq(self) -> None:
        self._eq_job = None
        if not self._root or not self._visible or not self._eq_active:
            self._draw_eq(False)
            return
        self._eq_phase += 0.45
        self._draw_eq(True)
        try:
            self._eq_job = self._root.after(90, self._animate_eq)
        except Exception:
            self._eq_job = None

    def _post(self, callback: Callable[[], None]) -> None:
        if not self._root:
            return
        try:
            self._root.after(0, callback)
        except Exception:
            pass


class OverrideManager(ctk.CTkToplevel):
    """Small list of every saved cover override, with per-row removal."""

    def __init__(
        self,
        master,
        repo: SongOverrideRepository,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._repo = repo
        self._on_change = on_change

        self.title("LastfmPresence - Carátulas personalizadas")
        self.geometry("470x500")
        self.configure(fg_color=theme.INK)
        self.transient(master)
        theme.set_window_icon(self)
        self._build()
        self._render()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(60, self._center_over, master)

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.INK, corner_radius=0)
        header.pack(fill="x", padx=24, pady=(20, 14))

        ctk.CTkLabel(
            header,
            text="Carátulas personalizadas",
            font=theme.font("display-lg", "bold", display=True),
            text_color=theme.PAPER,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            header,
            text="Se aplican cuando suena cada canción.",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        ctk.CTkFrame(self, height=1, fg_color=theme.BORDER, corner_radius=0).pack(fill="x")

        self._list = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.INK,
            border_width=1,
            border_color=theme.BORDER,
            corner_radius=10,
            width=400,
            height=330,
        )
        self._list.pack(fill="both", expand=True, padx=20, pady=14)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 18))

        self._count_label = ctk.CTkLabel(
            footer,
            text="",
            font=theme.font("small"),
            text_color=theme.MUTED,
            anchor="w",
        )
        self._count_label.pack(side="left")

        ctk.CTkButton(
            footer,
            text="Cerrar",
            command=self.destroy,
            width=86,
            height=32,
            font=theme.font("small"),
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.LABEL,
            corner_radius=8,
            border_width=1,
            border_color=theme.BORDER,
        ).pack(side="right")

    def _render(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()

        try:
            overrides = self._repo.all()
        except Exception:
            logger.exception("Could not read artwork overrides")
            overrides = []

        if not overrides:
            ctk.CTkLabel(
                self._list,
                text="Todavía no has personalizado ninguna carátula.",
                font=theme.font("small"),
                text_color=theme.MUTED,
                wraplength=320,
                justify="center",
            ).pack(pady=60)
            self._count_label.configure(text="0 personalizadas")
            return

        for override in overrides:
            row = ctk.CTkFrame(
                self._list,
                fg_color=theme.PANEL,
                corner_radius=9,
                border_width=1,
                border_color=theme.BORDER,
            )
            row.pack(fill="x", pady=(0, 6), padx=4)

            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=9)

            ctk.CTkLabel(
                text,
                text=override.title,
                font=theme.font("body", "bold"),
                text_color=theme.PAPER,
                anchor="w",
                justify="left",
                wraplength=300,
            ).pack(fill="x")

            ctk.CTkLabel(
                text,
                text=f"{override.artist} · {SOURCE_LABELS.get(override.source, override.source)}",
                font=theme.font("small"),
                text_color=theme.MUTED,
                anchor="w",
                justify="left",
                wraplength=300,
            ).pack(fill="x", pady=(1, 0))

            ctk.CTkButton(
                row,
                text="",
                image=theme.icon("close", 12, theme.LABEL),
                command=lambda o=override: self._remove(o),
                width=30,
                height=30,
                fg_color="transparent",
                hover_color=theme.HOVER,
                corner_radius=7,
                border_width=0,
            ).pack(side="right", padx=(0, 8))

        count = len(overrides)
        self._count_label.configure(
            text="1 personalizada" if count == 1 else f"{count} personalizadas"
        )

    def _remove(self, override: SongOverride) -> None:
        try:
            self._repo.remove(override.artist, override.title)
        except Exception:
            logger.exception("Could not remove artwork override from manager")
            return
        self._render()
        self._on_change()

    def _center_over(self, master) -> None:
        try:
            master.update_idletasks()
            width, height = 470, 500
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
            self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass


def run_player_window(
    on_open_config: Optional[Callable[[], None]] = None,
    on_config_saved: Optional[Callable[[], None]] = None,
) -> None:
    PlayerWindow(on_open_config=on_open_config, on_config_saved=on_config_saved).show()



