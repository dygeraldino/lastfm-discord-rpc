# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop

Windows 10/11 desktop app built with customtkinter; tray-resident, no browser surface.

## Users

People who already scrobble everything they listen to — via Web Scrobbler in the browser, the Last.fm mobile app, or streaming integrations — and who keep Discord open on a Windows desktop. They want their Discord profile to show the same track without leaving the music app or touching a client mod.

## Product Purpose

LastfmPresence mirrors the user's current Last.fm track into Discord Rich Presence: title, artist, album, artwork and link buttons. It exists so the status is accurate with almost no attention. Success is glancing at Discord (or at the player window) and seeing the right track and the right cover while the music keeps playing elsewhere.

## Positioning

A local tray daemon that reads public Last.fm scrobbles, repairs missing or wrong artwork through a fallback pipeline, and lets the user pin a cover per song. It is not a player, a scrobbler, or a Discord client mod.

## Operating Context

- Music plays in another application; LastfmPresence only reads Last.fm's recent-tracks feed.
- The app lives in the Windows notification area; the player view is a read-only mirror of what Last.fm reports.
- Discord desktop must be running for presence to appear.
- Last.fm's "Hide recent listening information" privacy option must stay unchecked or the feed is empty.
- Configuration is rare; the player is the everyday surface.
- All UI copy is Spanish.

## Capabilities and Constraints

- Windows-only, single instance, PyInstaller one-file build.
- Polls Last.fm on an interval; no playback control, seek, volume or queue management.
- Discord Rich Presence only accepts reachable online image URLs, never local files.
- Fallback artwork: persistent cache → Deezer → MusicBrainz/Cover Art Archive.
- Per-song overrides choose between Last.fm base, Deezer, MusicBrainz or
  "Sin portada" (no artwork sent to Discord); stored at `%APPDATA%\LastfmPresence\song_overrides.json`.
- The player window shows the current track plus a short recent-history list from Last.fm.
- Closing the player hides it to the tray; the daemon keeps running. First run opens configuration because there are no credentials yet.
- Configuration opens from a gear in the player; the tray also exposes it.

## Brand Commitments

- Name: LastfmPresence.
- Logo: aquamarine disc with black line-art music player and tangled earphones; dominant colour sampled at `#6FFFE4`.
- The aquamarine from the logo is the app's base accent; black/ink and off-white support it.
- Spanish-language interface.
- The product should feel like a music player, not a settings utility or a developer tool.

## Evidence on Hand

- Logo asset: `src/presentation/gui/assets/icon.ico` (16–256 px, aquamarine `#6FFFE4` ground, black line art).
- Real product copy and feature set documented in `README.md` and `AGENTS.md`.
- No customer testimonials, benchmarks, pricing or commercial claims exist; future work must not invent them.

## Product Principles

1. Mirror, never control: the interface reports what Last.fm says and never pretends to play, pause or queue.
2. The status is the product: track and cover should be readable at a glance from across the room.
3. Tell the truth about state: paused, not playing, loading and error look different and say so.
4. The everyday surface is the player; configuration stays one deliberate step away.
5. Local-first and quiet: the app lives in the tray, does not interrupt, and never ships a broken cover silently.

## Accessibility & Inclusion

- Keyboard focus visible on every control; no colour-only status.
- Body and control text must meet 4.5:1 against its surface.
- Respect Windows display scaling; avoid fixed layouts that clip at 125–150%.
