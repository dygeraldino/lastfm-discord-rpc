from typing import Optional

import pytest

from src.application.services.override_aware_music_provider import OverrideAwareMusicProvider
from src.domain.entities.song_override import SongOverride
from src.domain.entities.track import Track
from src.domain.interfaces.music_provider import MusicProvider


class FakeMusicProvider(MusicProvider):
    def __init__(self, track: Optional[Track]) -> None:
        self._track = track
        self.closed = False

    async def get_current_track(self) -> Optional[Track]:
        return self._track

    async def close(self) -> None:
        self.closed = True


class FakeOverrideRepository:
    def __init__(self, override: Optional[SongOverride] = None) -> None:
        self._override = override

    def get(self, artist: str, title: str) -> Optional[SongOverride]:
        return self._override

    def all(self):
        return [self._override] if self._override else []

    def save(self, override):
        self._override = override

    def remove(self, artist, title):
        self._override = None
        return True


def make_track() -> Track:
    return Track(
        title="Come Together",
        artist="The Beatles",
        album="Abbey Road",
        artwork_url="https://lastfm/base.jpg",
        is_playing=True,
    )


class TestOverrideAwareMusicProvider:
    @pytest.mark.asyncio
    async def test_applies_override_url(self):
        inner = FakeMusicProvider(make_track())
        overrides = FakeOverrideRepository(
            SongOverride("The Beatles", "Come Together", "deezer", "https://cdn/deezer.jpg")
        )
        provider = OverrideAwareMusicProvider(inner, overrides)

        track = await provider.get_current_track()

        assert track is not None
        assert track.artwork_url == "https://cdn/deezer.jpg"

    @pytest.mark.asyncio
    async def test_keeps_base_artwork_without_override(self):
        inner = FakeMusicProvider(make_track())
        provider = OverrideAwareMusicProvider(inner, FakeOverrideRepository())

        track = await provider.get_current_track()

        assert track is not None
        assert track.artwork_url == "https://lastfm/base.jpg"

    @pytest.mark.asyncio
    async def test_returns_none_when_inner_has_no_track(self):
        provider = OverrideAwareMusicProvider(FakeMusicProvider(None), FakeOverrideRepository())

        assert await provider.get_current_track() is None

    @pytest.mark.asyncio
    async def test_does_not_mutate_original_track(self):
        original = make_track()
        overrides = FakeOverrideRepository(
            SongOverride("The Beatles", "Come Together", "musicbrainz", "https://cdn/mb.jpg")
        )
        provider = OverrideAwareMusicProvider(FakeMusicProvider(original), overrides)

        await provider.get_current_track()

        assert original.artwork_url == "https://lastfm/base.jpg"

    @pytest.mark.asyncio
    async def test_close_delegates_to_inner(self):
        inner = FakeMusicProvider(make_track())
        provider = OverrideAwareMusicProvider(inner, FakeOverrideRepository())

        await provider.close()

        assert inner.closed is True
