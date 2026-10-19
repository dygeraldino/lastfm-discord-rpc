from src.infrastructure.providers.artwork_utils import is_placeholder_artwork
from src.infrastructure.providers.lastfm_recent_tracks import (
    LastFmFeedError,
    parse_recent_tracks,
)

REAL_IMAGE = "https://lastfm.freetls.fastly.net/i/u/300x300/abc123.jpg"
PLACEHOLDER_IMAGE = (
    "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png"
)


def _payload(*tracks: dict) -> dict:
    return {"recenttracks": {"track": list(tracks)}}


def test_parses_now_playing_and_scrobbles():
    payload = _payload(
        {
            "name": "Dios Se Ríe",
            "artist": {"#text": "Ale Zéguer"},
            "album": {"#text": "Dios Se Ríe"},
            "@attr": {"nowplaying": "true"},
            "image": [{"size": "extralarge", "#text": REAL_IMAGE}],
        },
        {
            "name": "Manos de Tijera",
            "artist": {"#text": "Camilo"},
            "album": {"#text": "Manos de Tijera"},
            "date": {"uts": "1729000000"},
            "image": [
                {"size": "large", "#text": REAL_IMAGE},
                {"size": "extralarge", "#text": PLACEHOLDER_IMAGE},
            ],
        },
    )

    tracks = parse_recent_tracks(payload)

    assert len(tracks) == 2
    assert tracks[0].artist == "Ale Zéguer"
    assert tracks[0].title == "Dios Se Ríe"
    assert tracks[0].album == "Dios Se Ríe"
    assert tracks[0].artwork_url == REAL_IMAGE
    assert tracks[0].now_playing is True
    assert tracks[0].played_at is None
    assert tracks[0].key == "ale zéguer::dios se ríe"

    assert tracks[1].artist == "Camilo"
    assert tracks[1].now_playing is False
    assert tracks[1].played_at == 1729000000
    assert tracks[1].artwork_url == REAL_IMAGE


def test_accepts_a_single_track_object():
    payload = _payload(
        {
            "name": "poquito",
            "artist": {"#text": "Valeria Castro"},
            "image": [{"size": "medium", "#text": REAL_IMAGE}],
        }
    )
    payload["recenttracks"]["track"] = payload["recenttracks"]["track"][0]

    tracks = parse_recent_tracks(payload)

    assert len(tracks) == 1
    assert tracks[0].title == "poquito"


def test_limits_the_number_of_tracks():
    payload = _payload(
        *[
            {
                "name": f"Song {index}",
                "artist": {"#text": "Artist"},
            }
            for index in range(6)
        ]
    )

    assert len(parse_recent_tracks(payload, limit=3)) == 3


def test_skips_tracks_without_title_or_artist():
    payload = _payload(
        {"name": "", "artist": {"#text": "Artist"}},
        {"name": "Title", "artist": {"#text": ""}},
        {"name": "Kept", "artist": {"#text": "Artist"}},
    )

    tracks = parse_recent_tracks(payload)

    assert [track.title for track in tracks] == ["Kept"]


def test_uses_no_artwork_when_every_size_is_a_placeholder():
    payload = _payload(
        {
            "name": "Song",
            "artist": {"#text": "Artist"},
            "image": [{"size": "extralarge", "#text": PLACEHOLDER_IMAGE}],
        }
    )

    assert parse_recent_tracks(payload)[0].artwork_url == ""


def test_raises_a_user_facing_error_for_api_errors():
    try:
        parse_recent_tracks({"error": 6, "message": "User not found"})
    except LastFmFeedError as exc:
        assert "User not found" in str(exc)
    else:
        raise AssertionError("Expected LastFmFeedError")


def test_malformed_payload_returns_an_empty_list():
    assert parse_recent_tracks({}) == []
    assert parse_recent_tracks({"recenttracks": None}) == []


def test_placeholder_helper_recognizes_known_hashes():
    assert is_placeholder_artwork(PLACEHOLDER_IMAGE) is True
    assert is_placeholder_artwork(REAL_IMAGE) is False
    assert is_placeholder_artwork("") is True
