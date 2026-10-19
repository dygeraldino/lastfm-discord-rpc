import json

import pytest

from src.domain.entities.song_override import SongOverride
from src.infrastructure.persistence.json_song_override_repository import (
    JsonSongOverrideRepository,
    slugify,
)


@pytest.fixture
def repo(tmp_path):
    return JsonSongOverrideRepository(path=tmp_path / "song_overrides.json")


class TestSlugify:
    def test_lowercases_and_replaces_spaces(self):
        assert slugify("The Beatles") == "the_beatles"

    def test_removes_special_characters(self):
        assert slugify("AC/DC & Friends") == "acdc_friends"

    def test_handles_parentheses(self):
        assert slugify("Album (Deluxe)") == "album_deluxe"


class TestJsonSongOverrideRepository:
    def test_get_missing_returns_none(self, repo):
        assert repo.get("Artist", "Title") is None

    def test_save_and_get_roundtrip(self, repo):
        override = SongOverride("Artist", "Title", "deezer", "https://cdn/cover.jpg")
        repo.save(override)

        result = repo.get("Artist", "Title")
        assert result == override

    def test_lookup_is_case_insensitive_via_slug(self, repo):
        repo.save(SongOverride("The Beatles", "Come Together", "deezer", "https://cdn/cover.jpg"))
        assert repo.get("the beatles", "come together") is not None

    def test_save_overwrites_existing(self, repo):
        repo.save(SongOverride("Artist", "Title", "deezer", "https://cdn/a.jpg"))
        repo.save(SongOverride("Artist", "Title", "musicbrainz", "https://cdn/b.jpg"))

        result = repo.get("Artist", "Title")
        assert result.source == "musicbrainz"
        assert result.url == "https://cdn/b.jpg"
        assert len(repo.all()) == 1

    def test_remove(self, repo):
        repo.save(SongOverride("Artist", "Title", "base", "https://cdn/a.jpg"))

        assert repo.remove("Artist", "Title") is True
        assert repo.get("Artist", "Title") is None
        assert repo.remove("Artist", "Title") is False

    def test_all_is_sorted(self, repo):
        repo.save(SongOverride("Zeta", "Song", "deezer", "https://cdn/z.jpg"))
        repo.save(SongOverride("Alpha", "Song", "deezer", "https://cdn/a.jpg"))

        assert [o.artist for o in repo.all()] == ["Alpha", "Zeta"]

    def test_persists_to_disk(self, repo, tmp_path):
        repo.save(SongOverride("Artist", "Title", "deezer", "https://cdn/a.jpg"))

        data = json.loads((tmp_path / "song_overrides.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        entry = next(iter(data.values()))
        assert entry["source"] == "deezer"
        assert entry["url"] == "https://cdn/a.jpg"

    def test_invalid_source_rejected(self, repo):
        with pytest.raises(ValueError):
            repo.save(SongOverride("Artist", "Title", "custom", "https://cdn/a.jpg"))

    def test_malformed_file_returns_empty(self, repo, tmp_path):
        path = tmp_path / "song_overrides.json"
        path.write_text("not json", encoding="utf-8")

        assert repo.get("Artist", "Title") is None
        assert repo.all() == []

    def test_invalid_entries_are_ignored(self, repo, tmp_path):
        path = tmp_path / "song_overrides.json"
        path.write_text(
            json.dumps(
                {
                    "a:b": {"artist": "A", "title": "B", "source": "bogus", "url": "x"},
                    "c:d": {"artist": "C"},
                }
            ),
            encoding="utf-8",
        )

        assert repo.all() == []

    def test_empty_artist_or_title_returns_none(self, repo):
        assert repo.get("", "Title") is None
        assert repo.get("Artist", "") is None
