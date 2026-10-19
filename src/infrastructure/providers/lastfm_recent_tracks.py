"""Reads the user's recent Last.fm tracks for the player view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from src.infrastructure.providers.artwork_utils import is_placeholder_artwork

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
IMAGE_SIZES = ("extralarge", "large", "medium", "small")


class LastFmFeedError(Exception):
    """A user-facing error while reading the recent-tracks feed."""


@dataclass(frozen=True, slots=True)
class RecentTrack:
    artist: str
    title: str
    album: str = ""
    artwork_url: str = ""
    now_playing: bool = False
    played_at: Optional[int] = None

    @property
    def key(self) -> str:
        return f"{self.artist.strip().lower()}::{self.title.strip().lower()}"

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("#text") or value.get("name") or "")
    return str(value or "")


def _pick_image(item: dict) -> str:
    images = item.get("image") or []
    if isinstance(images, dict):
        images = [images]
    for size in IMAGE_SIZES:
        for image in images:
            if not isinstance(image, dict):
                continue
            if image.get("size") == size and image.get("#text"):
                url = str(image.get("#text"))
                if not is_placeholder_artwork(url):
                    return url
    return ""


def parse_recent_tracks(payload: dict, limit: int = 8) -> list[RecentTrack]:
    if not isinstance(payload, dict):
        raise LastFmFeedError("Last.fm devolvió una respuesta inesperada.")

    if "error" in payload:
        message = payload.get("message") or "Last.fm rechazó la petición."
        raise LastFmFeedError(str(message))

    recent = payload.get("recenttracks") or {}
    if not isinstance(recent, dict):
        return []
    raw_tracks = recent.get("track", [])
    if isinstance(raw_tracks, dict):
        raw_tracks = [raw_tracks]
    if not isinstance(raw_tracks, list):
        return []

    tracks: list[RecentTrack] = []
    for item in raw_tracks:
        if not isinstance(item, dict):
            continue

        title = str(item.get("name") or "").strip()
        artist = _text(item.get("artist")).strip()
        if not title or not artist:
            continue

        played_at: Optional[int] = None
        date_value = item.get("date")
        if isinstance(date_value, dict):
            raw_uts = date_value.get("uts")
            if raw_uts not in (None, ""):
                try:
                    played_at = int(raw_uts)
                except (TypeError, ValueError):
                    played_at = None

        attr = item.get("@attr")
        now_playing = isinstance(attr, dict) and str(
            attr.get("nowplaying", "")
        ).lower() == "true"

        tracks.append(
            RecentTrack(
                artist=artist,
                title=title,
                album=_text(item.get("album")).strip(),
                artwork_url=_pick_image(item),
                now_playing=now_playing,
                played_at=played_at,
            )
        )
        if len(tracks) >= limit:
            break

    return tracks


class LastFmRecentTracksClient:
    """Small synchronous client; call it from a worker thread."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def fetch(self, username: str, api_key: str, limit: int = 8) -> list[RecentTrack]:
        if not username or not api_key:
            raise LastFmFeedError("Faltan las credenciales de Last.fm.")

        params = {
            "method": "user.getRecentTracks",
            "user": username,
            "api_key": api_key,
            "format": "json",
            "limit": max(1, limit),
            "extended": 1,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(LASTFM_API_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LastFmFeedError("No se pudo conectar con Last.fm.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise LastFmFeedError("Last.fm devolvió una respuesta ilegible.") from exc

        return parse_recent_tracks(payload, limit=limit)
