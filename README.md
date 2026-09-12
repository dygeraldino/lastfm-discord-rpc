# Last.fm → Discord Rich Presence Daemon

A robust background daemon that syncs your currently playing track from Last.fm to Discord Rich Presence.

## Features

- **Clean Architecture** - Strict separation of Domain, Application, Infrastructure, and Daemon layers
- **Dependency Inversion** - Interfaces (ports) in domain, implementations in infrastructure
- **Resilient Polling** - Exponential backoff, rate-limit handling, never crashes on network errors
- **Graceful Shutdown** - Handles SIGINT/SIGTERM, clears Discord presence on exit
- **Structured Logging** - Loguru with daily rotation, separate error logs
- **Type Safety** - Full type hints, Pydantic validation

## Requirements

- Python 3.11+
- Last.fm API account
- Discord Developer Application

## Installation

```bash
pip install -r requirements.txt

# Linux / macOS / Git Bash
cp .env.example .env

# Windows (CMD / PowerShell)
copy .env.example .env
# or in PowerShell: Copy-Item .env.example .env

# Edit .env with your credentials
```

## Configuration

Create a `.env` file with:

```env
LASTFM_API_KEY=your_lastfm_api_key
LASTFM_USERNAME=your_lastfm_username
DISCORD_CLIENT_ID=your_discord_application_client_id
POLL_INTERVAL=30
LOG_LEVEL=INFO
```

### Getting Credentials

1. **Last.fm API Key**: https://www.last.fm/api/account/create
2. **Discord Client ID**: https://discord.com/developers/applications → New Application → Copy Application ID

## Running

```bash
# Foreground (for testing)
python main.py

# Background (Windows Task Scheduler)
pythonw.exe main.py
```

### Windows Task Scheduler Setup

1. Open Task Scheduler → Create Basic Task
2. Trigger: "At log on"
3. Action: Start a program
   - Program: `pythonw.exe` (full path, e.g., `C:\Python311\pythonw.exe`)
   - Arguments: `C:\path\to\lastfm-discord-rpc\main.py`
   - Start in: `C:\path\to\lastfm-discord-rpc`
4. Finish

## Architecture

```
src/
├── domain/                 # Pure business logic, no external deps
│   ├── entities/Track.py
│   ├── interfaces/
│   │   ├── MusicProvider   # Port for music data
│   │   └── PresencePublisher  # Port for Discord RPC
│   └── exceptions/
├── application/            # Use cases, orchestrates domain
│   ├── use_cases/SyncPresenceUseCase
│   └── dtos/TrackDTO
├── infrastructure/         # External adapters
│   ├── providers/LastFmClient      # Implements MusicProvider
│   └── publishers/DiscordRpcPublisher  # Implements PresencePublisher
├── daemon/                 # Long-running process
│   ├── runner.py           # Async loop with error handling
│   └── signal_handler.py   # SIGINT/SIGTERM handling
└── config/
    ├── settings.py         # Pydantic settings
    └── logging_config.py   # Loguru configuration
```

## Testing

```bash
# Using pytest directly
pytest tests/ -v

# Or via Python launcher (Windows)
py -m pytest tests/ -v
```

## Logging

Logs are written to `logs/`:
- `daemon_YYYY-MM-DD.log` - All logs (rotated daily, kept 30 days)
- `errors_YYYY-MM-DD.log` - Errors only (rotated daily, kept 90 days)

## License

MIT