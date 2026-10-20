from dataclasses import dataclass
from typing import Optional


VALID_SOURCES = ("base", "deezer", "musicbrainz", "none")


@dataclass(frozen=True, slots=True)
class SongOverride:
    artist: str
    title: str
    source: str
    url: Optional[str] = None

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"
