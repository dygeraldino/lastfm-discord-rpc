# LastfmPresence

**LastfmPresence** is a lightweight Windows desktop application that seamlessly bridges your active Last.fm listening activity with Discord Rich Presence. It displays your currently playing track as a Discord status, complete with high-resolution album artwork, track/artist/album details, and interactive profile buttons ("Listen on Last.fm" and "View Artist").

> **Important Considerations:**
> - **Not a Scrobbler or Music Player:** LastfmPresence **does not scrobble tracks** or play audio. It is designed specifically for users who **already scrobble** to Last.fm using external integrations (such as *Web Scrobbler*, official mobile apps, or direct streaming service connections like Spotify or Apple Music).
> - **No Discord Client Mods Required:** Built for users who want custom Last.fm status integration **without using modified Discord clients**.

## Installation Methods

### Method 1: Download Pre-compiled Release (Recommended)

1. Download `LastfmPresence_Setup_v1.0.2_x64.exe` (or `LastfmPresence_Portable_v1.0.2.exe`) from the latest [release](https://github.com/dygeraldino/lastfm-discord-rpc/releases)
2. Run the installer or launch the portable executable directly
3. Choose whether to start automatically at login (Installer option)
4. Launch from Start Menu or system tray

### Method 2: Compile the Executable & Installer Yourself

**Requirements:**

- Python 3.11+
- Git
- Inno Setup 6+ (optional, for installer)

```bash
# Clone the repository
git clone https://github.com/dygeraldino/lastfm-discord-rpc.git
cd lastfm-discord-rpc

# Install build dependencies
pip install -r requirements.txt
pip install pyinstaller

# Build the standalone executable + Windows installer (if Inno Setup is installed)
python build.py

# Outputs in dist/:
# - dist/LastfmPresence.exe (~54 MB) - Base standalone executable output by PyInstaller
# - dist/LastfmPresence_Portable_v1.0.1.exe (~54 MB) - Versioned portable executable (ready for direct releases)
# - dist/LastfmPresence_Setup_v1.0.1_x64.exe (~50 MB) - Official Windows installer (if Inno Setup found)

# Run directly - opens config window on first launch
dist\LastfmPresence.exe
```

> **Build Outputs & Distinction:**
> - **`LastfmPresence.exe`**: Base binary compiled by PyInstaller. Inno Setup uses this file to package the installer.
> - **`LastfmPresence_Portable_v1.0.1.exe`**: Identical binary to `LastfmPresence.exe`, renamed with version details for portable usage (no installation required).
> - **`LastfmPresence_Setup_v1.0.1_x64.exe`**: Official Windows installer created via Inno Setup (adds Start Menu shortcuts and optional Windows auto-start).

### Method 3: Run from Source (Python + Task Scheduler)

**Requirements:**

- Python 3.11+
- Last.fm API account
- Discord Developer Application

```bash
# Clone and install dependencies
git clone https://github.com/dygeraldino/lastfm-discord-rpc.git
cd lastfm-discord-rpc
pip install -r requirements.txt

# Configure environment
# Windows (PowerShell)
Copy-Item .env.example .env

# Edit .env with your credentials
# LASTFM_API_KEY=your_key
# LASTFM_USERNAME=your_username
# DISCORD_CLIENT_ID=your_client_id
# POLL_INTERVAL=30
```

**Run in foreground (testing):**

```bash
python main.py
```

**Run in background via Windows Task Scheduler:**

1. Open **Task Scheduler** → **Create Basic Task**
2. Name: `LastfmPresence` → Next
3. Trigger: **At log on** → Next
4. Action: **Start a program** → Next
5. Program: `pythonw.exe` (full path, e.g., `C:\Python311\pythonw.exe`)
6. Arguments: `C:\path\to\lastfm-discord-rpc\main.py`
7. Start in: `C:\path\to\lastfm-discord-rpc`
8. Finish

> **Note:** Method 3 uses `.env` file configuration. Methods 1 & 2 use a JSON config file at `%APPDATA%\LastfmPresence\config.json` managed by the GUI.

## Configuration

### Important: Last.fm Privacy Settings

> **This directly affects the application functionality.**

If you enable **"Hide recent listening information"** in your [Last.fm Privacy Settings](https://www.last.fm/settings/privacy), the app will **stop working**.

**Why it breaks:** The daemon queries the public `user.getRecentTracks` endpoint using your username and API key. When this privacy option is enabled, Last.fm hides your real-time scrobbles from all public API calls. The daemon receives an empty track list and cannot detect what you're listening to.

**Fix:** Keep **"Hide recent listening information" unchecked** so your recent tracks remain publicly accessible via the API.

### Getting Credentials

1. **Last.fm API Key**: https://www.last.fm/api/account/create
2. **Discord Client ID**: https://discord.com/developers/applications → New Application → Copy Application ID

### Configuration Options

| Setting                        | Default    | Description                                        |
| ------------------------------ | ---------- | -------------------------------------------------- |
| `lastfm_username`              | _required_ | Your Last.fm username                              |
| `lastfm_api_key`               | _required_ | Your Last.fm API key                               |
| `discord_client_id`            | _required_ | Discord Application Client ID                      |
| `poll_interval`                | `30`       | Seconds between Last.fm polls                      |
| `log_level`                    | `INFO`     | Log level (DEBUG, INFO, WARNING, ERROR)            |
| `enable_rich_presence_buttons` | `true`     | Show "Listen on Last.fm" and "View Artist" buttons |
| `enable_fallback_artwork`      | `true`     | Enable Deezer & MusicBrainz fallback artwork lookup|

### Player and Settings

Click the tray icon (or **Abrir reproductor** in its menu) to open the player. It shows the current Last.fm track, a live equalizer, the most recent unique tracks, and the three artwork sources for the song. Closing the window hides it to the tray; the daemon keeps running.

Use the gear in the player header to open **Ajustes** (or **Ajustes** in the tray menu). The settings window covers the Last.fm/Discord credentials, the poll interval and the fallback-artwork switch. Saving applies the changes and restarts the presence daemon without quitting the app.

### Per-Song Artwork

Open the player, find the track under **Carátula**, preview the artwork available from Last.fm, Deezer, MusicBrainz **and the app logo ("Sin portada")**, choose one, and press **Guardar carátula**. The choice is stored in `%APPDATA%\LastfmPresence\song_overrides.json` and applied whenever that `artist + title` plays. The footer link lists every saved override so you can remove them.

- **Identity**: `artist + title` (album is ignored, so live/remaster variants share the override)
- **Sources**: Last.fm base image, Deezer, MusicBrainz/Cover Art Archive, and **"Sin portada"** (shows the app logo in both the player and Discord; no image is sent to Discord)
- **Preview**: Four source tiles with thumbnails; missing candidates are disabled
- **Storage**: `%APPDATA%\LastfmPresence\song_overrides.json` (`{source, url}` per slugified `artist:title` key; `url` is null for "Sin portada")
- **Precedence**: An override wins over the normal pipeline; without an override the fallback flow is untouched
- **Runtime**: `OverrideAwareMusicProvider` re-reads the override file on every poll, so edits apply to the next detected track change; selecting "Sin portada" sends no `large_image` to Discord
- **Removal**: "Quitar" in the player, or the footer manager listing every saved override
- **No local files**: Only online URLs are used (Discord Rich Presence requires a reachable image URL); "Sin portada" is the exception and shows no image anywhere

## Testing

```bash
# Using pytest directly
pytest tests/ -v

# Or via Python launcher (Windows)
py -m pytest tests/ -v
```

## Logs

Logs are written to `%APPDATA%\LastfmPresence\logs\`:

- `daemon_YYYY-MM-DD.log` - All logs (rotated daily, kept 30 days)
- `errors_YYYY-MM-DD.log` - Errors only (rotated daily, kept 90 days)

Open logs from the system tray menu: **Abrir logs**

## License

MIT
