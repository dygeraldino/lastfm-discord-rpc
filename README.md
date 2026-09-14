# LastfmPresence

LastfmPresence is a Windows desktop application that bridges your Last.fm listening activity with Discord Rich Presence. It displays your currently playing track as a Discord status, complete with album artwork, track/artist/album details, and interactive buttons to "Listen on Last.fm" or "View Artist" directly from Discord.

Designed as a polished desktop app rather than a raw script, it includes a dark-mode GUI for first-time configuration (no manual .env editing), a system tray icon for background operation, structured logging to `%APPDATA%`, and a standalone ~53 MB executable that requires no Python installation. An Inno Setup installer is also available for proper Windows integration with Start Menu shortcuts and optional auto-start on login.

Under the hood, it follows Clean Architecture with strict layer separation (Domain, Application, Infrastructure, Daemon, Presentation), dependency inversion via interfaces, exponential backoff with 429 handling, graceful shutdown on SIGINT/SIGTERM, and full type safety with Pydantic validation.

## Installation Methods

### Method 1: Download Pre-compiled Release (Recommended)

1. Download `LastfmPresence_Setup_v1.0.1_x64.exe` (or `LastfmPresence_Portable_v1.0.1.exe`) from the latest [release](https://github.com/dygeraldino/lastfm-discord-rpc/releases)
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

Open logs from the system tray menu: **Open Logs**

## License

MIT
