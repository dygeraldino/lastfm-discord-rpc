import pytest
from src.domain.entities.track import Track
from datetime import datetime


class TestTrack:
    def test_track_creation_minimal(self):
        track = Track(title="Test Song", artist="Test Artist", is_playing=True)
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == ""
        assert track.artwork_url == ""
        assert track.is_playing is True
        assert track.timestamp is None

    def test_track_creation_full(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        track = Track(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            artwork_url="https://example.com/art.jpg",
            is_playing=True,
            timestamp=ts,
        )
        assert track.album == "Test Album"
        assert track.artwork_url == "https://example.com/art.jpg"
        assert track.timestamp == ts

    def test_track_equality_same(self):
        t1 = Track(title="Song", artist="Artist", is_playing=True)
        t2 = Track(title="Song", artist="Artist", is_playing=True)
        assert t1 == t2

    def test_track_equality_different_title(self):
        t1 = Track(title="Song 1", artist="Artist", is_playing=True)
        t2 = Track(title="Song 2", artist="Artist", is_playing=True)
        assert t1 != t2

    def test_track_equality_different_playing_state(self):
        t1 = Track(title="Song", artist="Artist", is_playing=True)
        t2 = Track(title="Song", artist="Artist", is_playing=False)
        assert t1 != t2

    def test_track_hash_consistency(self):
        t1 = Track(title="Song", artist="Artist", is_playing=True)
        t2 = Track(title="Song", artist="Artist", is_playing=True)
        assert hash(t1) == hash(t2)

    def test_display_name(self):
        track = Track(title="Song", artist="Artist")
        assert track.display_name == "Artist - Song"

    def test_hash_key_case_insensitive(self):
        t1 = Track(title="Song", artist="Artist", album="Album", is_playing=True)
        t2 = Track(title="song", artist="artist", album="album", is_playing=True)
        assert t1.hash_key == t2.hash_key

    def test_track_with_button_urls(self):
        buttons = [("Listen on Last.fm", "https://last.fm/track"), ("View Artist", "https://last.fm/artist")]
        track = Track(title="Song", artist="Artist", button_urls=buttons)
        assert track.button_urls == buttons

    def test_track_button_urls_default_empty(self):
        track = Track(title="Song", artist="Artist")
        assert track.button_urls == []