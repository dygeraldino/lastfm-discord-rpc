from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class Track:
    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""
    is_playing: bool = False
    timestamp: Optional[datetime] = None
    button_urls: list[tuple[str, str]] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.title, self.artist, self.album, self.is_playing))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Track):
            return NotImplemented
        return (
            self.title == other.title
            and self.artist == other.artist
            and self.album == other.album
            and self.is_playing == other.is_playing
        )

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"

    @property
    def hash_key(self) -> str:
        return f"{self.artist.lower()}:{self.title.lower()}:{self.album.lower()}:{str(self.is_playing).lower()}"