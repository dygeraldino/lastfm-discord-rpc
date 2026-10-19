from dataclasses import dataclass


VALID_SOURCES = ("base", "deezer", "musicbrainz")


@dataclass(frozen=True, slots=True)
class SongOverride:
    artist: str
    title: str
    source: str
    url: str

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"
