from unittest.mock import AsyncMock

import pytest

from src.application.services.candidate_artwork_service import CandidateArtworkService


class FakeProvider:
    def __init__(self, result):
        self._result = result
        self.closed = False
        self.get_artwork_url = AsyncMock(return_value=result)

    async def close(self):
        self.closed = True


class TestCandidateArtworkService:
    @pytest.mark.asyncio
    async def test_returns_all_candidates(self):
        deezer = FakeProvider("https://cdn/deezer.jpg")
        musicbrainz = FakeProvider("https://coverart/mb.jpg")
        service = CandidateArtworkService(deezer, musicbrainz)

        result = await service.get_candidates(
            "The Beatles", "Come Together", "Abbey Road", "https://lastfm/base.jpg"
        )

        assert result == {
            "base": "https://lastfm/base.jpg",
            "deezer": "https://cdn/deezer.jpg",
            "musicbrainz": "https://coverart/mb.jpg",
        }
        deezer.get_artwork_url.assert_awaited_once_with(
            "The Beatles", "Come Together", "Abbey Road"
        )
        musicbrainz.get_artwork_url.assert_awaited_once_with(
            "The Beatles", "Come Together", "Abbey Road"
        )

    @pytest.mark.asyncio
    async def test_missing_base_returns_none(self):
        service = CandidateArtworkService(FakeProvider(None), FakeProvider(None))

        result = await service.get_candidates("Artist", "Title")

        assert result == {"base": None, "deezer": None, "musicbrainz": None}

    @pytest.mark.asyncio
    async def test_provider_exception_does_not_break_other_candidates(self):
        deezer = FakeProvider(None)
        deezer.get_artwork_url = AsyncMock(side_effect=RuntimeError("boom"))
        musicbrainz = FakeProvider("https://coverart/mb.jpg")
        service = CandidateArtworkService(deezer, musicbrainz)

        result = await service.get_candidates("Artist", "Title")

        assert result["deezer"] is None
        assert result["musicbrainz"] == "https://coverart/mb.jpg"

    @pytest.mark.asyncio
    async def test_empty_artist_or_title_skips_providers(self):
        deezer = FakeProvider("https://cdn/deezer.jpg")
        service = CandidateArtworkService(deezer, FakeProvider(None))

        result = await service.get_candidates("", "Title", base_url="https://lastfm/base.jpg")

        assert result["base"] == "https://lastfm/base.jpg"
        deezer.get_artwork_url.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_closes_both_providers(self):
        deezer = FakeProvider(None)
        musicbrainz = FakeProvider(None)
        service = CandidateArtworkService(deezer, musicbrainz)

        await service.close()

        assert deezer.closed is True
        assert musicbrainz.closed is True
