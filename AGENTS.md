# LastfmPresence - Agent Instructions

## Project Overview

Windows desktop app bridging Last.fm listening activity to Discord Rich Presence. Clean Architecture (Domain, Application, Infrastructure, Daemon, Presentation). Uses system tray + dark-mode config GUI. Outputs standalone executable via PyInstaller, optional Inno Setup installer.

**Version: 1.0.2** — Adds per-song artwork overrides (Last.fm base, Deezer or MusicBrainz) from the config window, on top of the existing fallback artwork pipeline.

## Key Commands

### Development

```bash
# Install deps
pip install -r requirements.txt

# Run from source (uses .env file)
python main.py

# Run tests
pytest tests/ -v
# or
py -m pytest tests/ -v
```

### Build

```bash
# Build executable + installer (auto-detects Inno Setup)
pip install pyinstaller
python build.py

# Outputs:
# dist/LastfmPresence.exe
# dist/LastfmPresence_Portable_v1.0.2.exe
# dist/LastfmPresence_Setup_v1.0.2_x64.exe (if Inno Setup found)
```

## Architecture Notes

### Entry Points

- `main.py` - Application bootstrap, single-instance mutex, config check, tray app
- `src/presentation/gui/player_window.py` - Player/now-playing surface (first window from the tray)
- `src/presentation/gui/main_window.py` - Settings window (gear or tray menu; first run)
- `src/daemon/runner.py` - Background polling loop

### Config Priority (highest first)

1. Constructor/init args
2. `%APPDATA%\LastfmPresence\config.json` (GUI-managed, JSON)
3. Environment variables
4. `.env` file (source/dev only)
5. Defaults

### Logging

- `%APPDATA%\LastfmPresence\logs\`
- `daemon_YYYY-MM-DD.log` (30-day retention)
- `errors_YYYY-MM-DD.log` (90-day retention)
- Rotation at midnight, zip compression

## Important Constraints

### Last.fm Privacy Setting

**Critical:** If user enables "Hide recent listening information" in Last.fm privacy settings, the app **stops working** (public `user.getRecentTracks` returns empty). User must keep this **unchecked**.

### Single Instance

Uses global mutex `Global\LastfmPresence_SingleInstance_Mutex_Guid_1029`. Second instance exits silently.

### Packaged Path Handling

When frozen (PyInstaller), `sys._MEIPASS` used for assets. Working directory forced to exe parent folder in `main.py`.

### Hidden Imports for PyInstaller

List in `build.py`. Add new internal modules here if import errors occur in built exe.

## Testing

- `pytest tests/ -v` - all tests
- Fixtures: `tests/conftest.py` provides session-scoped event loop
- Unit tests under `tests/unit/` mirroring src structure

## Environment

- Python 3.11+
- Windows only (Win32 mutex, Inno Setup, APPDATA paths)
- Dependencies in `requirements.txt`

## Localization

The UI is bilingual: Spanish (default) and English. All user-facing strings are wrapped
with `t()` from `src/presentation/gui/locale.py`. The selected language is persisted in
`%APPDATA%\LastfmPresence\config.json` under the `language` key (`es` or `en`) and can be
changed from the **Idioma / Language** dropdown in Ajustes. Adding a new language means
adding a new entry to `TRANSLATIONS` in `locale.py`.

## Key Files to Know

| File                                                       | Purpose                                   |
| ---------------------------------------------------------- | ----------------------------------------- |
| `main.py`                                                  | App entry, wiring, single-instance        |
| `config/settings.py`                                       | Pydantic settings with JSON config source |
| `config/logging_config.py`                                 | Loguru setup with file rotation           |
| `build.py`                                                 | PyInstaller + Inno Setup build script     |
| `installer.iss`                                            | Inno Setup installer script               |
| `src/daemon/runner.py`                                     | Polling loop with graceful shutdown       |
| `src/presentation/gui/player_window.py`                    | Player/now-playing window + per-song covers |
| `src/presentation/gui/main_window.py`                      | Settings window (customtkinter)           |
| `src/presentation/gui/theme.py`                            | Palette, fonts, icons, cover rendering    |
| `src/infrastructure/providers/lastfm_recent_tracks.py`     | Recent-tracks feed used by the player     |
| `src/infrastructure/persistence/json_config_repository.py` | JSON config at `%APPDATA%`                |
| `src/domain/interfaces/artwork_provider.py`                | Fallback artwork provider interface       |
| `src/infrastructure/providers/deezer_client.py`           | Deezer API provider (primary CDN fallback)|
| `src/infrastructure/providers/musicbrainz_client.py`       | MusicBrainz + Cover Art Archive provider  |
| `src/infrastructure/providers/fallback_artwork_provider.py` | Composite artwork provider (Cache -> Deezer -> MB) |
| `src/infrastructure/persistence/json_artwork_cache_repository.py` | Persistent artwork cache at `%APPDATA%` |
| `src/application/services/candidate_artwork_service.py`     | Resolves base/Deezer/MusicBrainz candidates for the player |
| `src/application/services/override_aware_music_provider.py` | Decorator that applies per-song artwork overrides |
| `src/infrastructure/persistence/json_song_override_repository.py` | Per-song overrides at `%APPDATA%` |

## Fallback Artwork Feature

When Last.fm returns a track without artwork (or returns Last.fm default placeholder images), the app automatically resolves album art via a composite fallback pipeline:

- **Enabled by default** (`enable_fallback_artwork: true` in config)
- **Lookup Pipeline**:
  1. **Persistent Cache**: `%APPDATA%\LastfmPresence\cache\artwork_cache.json` (instant, no network)
  2. **Deezer API** (Primary): Fetches high-res `dzcdn.net` cover images which bypass Discord proxy hotlinking blocks
  3. **MusicBrainz + Cover Art Archive** (Secondary): Searches release MBID → Cover Art Archive (`front-500`)
- **Cache**: Stores positive image URLs or `null` for known misses (to avoid redundant API requests)
- **Rate limiting**: Enforces respectful API rate limits (Deezer 0.5s, MusicBrainz 1.0s)
- **User-Agent**: `LastfmPresence/1.0.0 (https://github.com/dygeraldino/lastfm-discord-rpc)`
- **GUI toggle**: Switch in **Ajustes** to enable/disable if desired
- **Scope**: Album/track artwork only (`large_image` in Discord RPC)

## Per-Song Artwork Overrides

The player (**Abrir reproductor** from the tray, or a click on the tray icon) lets the user pick the artwork source for the song currently shown under **Carátula**:

- **Identity**: `artist + title` (album is ignored, so live/remaster variants share the override)
- **Sources**: Last.fm base image, Deezer, MusicBrainz/Cover Art Archive, and **"Sin portada"** (shows the app logo in the player and sends no image to Discord)
- **Preview**: Four source tiles with thumbnails; missing candidates are disabled
- **Storage**: `%APPDATA%\LastfmPresence\song_overrides.json` (`{source, url}` per slugified `artist:title` key; `url` is null for `"none"`)
- **Precedence**: An override wins over the normal pipeline; without an override the fallback flow is untouched
- **Runtime**: `OverrideAwareMusicProvider` wraps `LastFmClient` and re-reads the override file on every poll, so edits apply to the next detected track change; selecting "Sin portada" sets `artwork_url=None` so Discord shows no image
- **Removal**: "Quitar" in the player, or the footer manager listing every saved override
- **No local files**: Only online URLs are used (Discord Rich Presence requires a reachable image URL); "Sin portada" is the exception and shows no image anywhere
