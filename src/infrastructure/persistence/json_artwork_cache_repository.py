import json
import os
import re
from pathlib import Path
from typing import Optional

from config.logging_config import get_logger


logger = get_logger(__name__)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text


class JsonArtworkCacheRepository:
    def __init__(self) -> None:
        appdata = os.getenv("APPDATA", "")
        self._cache_dir = Path(appdata) / "LastfmPresence" / "cache"
        self._cache_file = self._cache_dir / "artwork_cache.json"
        self._cache: dict[str, Optional[str]] = {}
        self._loaded = False

    def _ensure_dir(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if self._loaded:
            return
        self._ensure_dir()
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.debug(f"Loaded artwork cache from {self._cache_file}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load artwork cache: {e}")
                self._cache = {}
        self._loaded = True

    def _save(self) -> None:
        self._ensure_dir()
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved artwork cache to {self._cache_file}")
        except OSError as e:
            logger.error(f"Failed to save artwork cache: {e}")

    def _make_key(self, artist: str, title: str) -> str:
        return f"{slugify(artist)}:{slugify(title)}"

    def get(self, artist: str, title: str) -> Optional[str]:
        self._load()
        key = self._make_key(artist, title)
        return self._cache.get(key)

    def get_entry(self, artist: str, title: str) -> tuple[bool, Optional[str]]:
        """Returns (is_found, artwork_url). is_found is True even if artwork_url is None (cached negative lookup)."""
        self._load()
        key = self._make_key(artist, title)
        if key in self._cache:
            return True, self._cache[key]
        return False, None

    def set(self, artist: str, title: str, url: Optional[str]) -> None:
        self._load()
        key = self._make_key(artist, title)
        self._cache[key] = url
        self._save()