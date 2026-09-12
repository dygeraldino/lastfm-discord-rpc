import pytest
from src.application.dtos.track_dto import TrackDTO, track_to_dto
from src.domain.entities.track import Track
from datetime import datetime


class TestTrackDTO:
    def test_dto_creation_minimal(self):
        dto = TrackDTO(title="Test Song", artist="Test Artist", is_playing=True)
        assert dto.title == "Test Song"
        assert dto.artist == "Test Artist"
        assert dto.album == ""
        assert dto.artwork_url == ""
        assert dto.is_playing is True
        assert dto.timestamp is None

    def test_dto_creation_full(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        dto = TrackDTO(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            artwork_url="https://example.com/art.jpg",
            is_playing=True,
            timestamp=ts,
        )
        assert dto.album == "Test Album"
        assert dto.artwork_url == "https://example.com/art.jpg"
        assert dto.timestamp == ts

    def test_dto_hash_key(self):
        dto = TrackDTO(title="Song", artist="Artist", album="Album", is_playing=True)
        assert dto.hash_key == "artist:song:album:true"

    def test_dto_to_track(self):
        dto = TrackDTO(title="Song", artist="Artist", is_playing=True)
        track = dto.to_track()
        assert isinstance(track, Track)
        assert track.title == "Song"
        assert track.artist == "Artist"
        assert track.is_playing is True

    def test_track_to_dto(self):
        track = Track(title="Song", artist="Artist", album="Album", is_playing=True)
        dto = track_to_dto(track)
        assert isinstance(dto, TrackDTO)
        assert dto.title == "Song"
        assert dto.artist == "Artist"
        assert dto.album == "Album"
        assert dto.is_playing is True