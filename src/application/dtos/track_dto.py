from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class TrackDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""
    is_playing: bool = False
    timestamp: Optional[datetime] = None

    @property
    def hash_key(self) -> str:
        return f"{self.artist.lower()}:{self.title.lower()}:{self.album.lower()}:{str(self.is_playing).lower()}"

    def to_track(self) -> "Track":
        from src.domain.entities.track import Track
        return Track(
            title=self.title,
            artist=self.artist,
            album=self.album,
            artwork_url=self.artwork_url,
            is_playing=self.is_playing,
            timestamp=self.timestamp,
        )


def track_to_dto(track: "Track") -> TrackDTO:
    return TrackDTO(
        title=track.title,
        artist=track.artist,
        album=track.album,
        artwork_url=track.artwork_url,
        is_playing=track.is_playing,
        timestamp=track.timestamp,
    )