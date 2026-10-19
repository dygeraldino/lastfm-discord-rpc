import json
import os
import re
from pathlib import Path
from typing import Optional

from src.domain.entities.song_override import VALID_SOURCES, SongOverride
from src.domain.interfaces.song_override_repository import SongOverrideRepository
from config.logging_config import get_logger


logger = get_logger(__name__)

APP_CONFIG_DIR = "LastfmPresence"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text


class JsonSongOverrideRepository(SongOverrideRepository):
    """Per-track artwork overrides stored in %APPDATA%\\LastfmPresence\\song_overrides.json.

    The file is read fresh on every lookup so the daemon picks up changes made
    from the config window without a restart.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or (
            Path(os.getenv("APPDATA", "")) / APP_CONFIG_DIR / "song_overrides.json"
        )

    def _make_key(self, artist: str, title: str) -> str:
        return f"{slugify(artist)}:{slugify(title)}"

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read song overrides: {e}")
            return {}

    def _write(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"Failed to write song overrides: {e}")
            raise

    @staticmethod
    def _to_override(entry: dict) -> Optional[SongOverride]:
        try:
            artist = str(entry["artist"])
            title = str(entry["title"])
            source = str(entry["source"])
            url = str(entry["url"])
        except (KeyError, TypeError):
            return None
        if source not in VALID_SOURCES or not url:
            return None
        return SongOverride(artist=artist, title=title, source=source, url=url)

    def get(self, artist: str, title: str) -> Optional[SongOverride]:
        if not artist or not title:
            return None
        entry = self._read().get(self._make_key(artist, title))
        if not isinstance(entry, dict):
            return None
        return self._to_override(entry)

    def all(self) -> list[SongOverride]:
        overrides = []
        for entry in self._read().values():
            if isinstance(entry, dict):
                override = self._to_override(entry)
                if override:
                    overrides.append(override)
        return sorted(overrides, key=lambda o: (o.artist.lower(), o.title.lower()))

    def save(self, override: SongOverride) -> None:
        if override.source not in VALID_SOURCES:
            raise ValueError(f"Invalid artwork source: {override.source}")
        data = self._read()
        data[self._make_key(override.artist, override.title)] = {
            "artist": override.artist,
            "title": override.title,
            "source": override.source,
            "url": override.url,
        }
        self._write(data)
        logger.info(f"Saved artwork override for {override.display_name} ({override.source})")

    def remove(self, artist: str, title: str) -> bool:
        key = self._make_key(artist, title)
        data = self._read()
        if key not in data:
            return False
        del data[key]
        self._write(data)
        logger.info(f"Removed artwork override for {artist} - {title}")
        return True
