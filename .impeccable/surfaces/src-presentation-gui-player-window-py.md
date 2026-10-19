---
version: 1
slug: "src-presentation-gui-player-window-py"
primary_target: "src/presentation/gui/player_window.py"
related_targets: ["src/presentation/gui/main_window.py"]
---

# Surface brief — Now Spinning

**Scope:** the app's main window (now playing + cover choice) and the settings window.
**Mode:** Operate. The user is checking what is mirrored to Discord and, when needed, fixing the cover; configuration is rare.

**Audience and job:** a Windows user who scrobbles everything to Last.fm and keeps Discord open. They open the app from the tray to confirm the right track and cover are live, occasionally pin a different cover for one song, and otherwise close it.

**Chosen direction:** "Now Spinning" — a late-night listening console. Pinned by the brief: the covers view must read as a music player, keep the logo's aquamarine `#6FFFE4`, and become the first surface opened from the tray; settings live behind a gear. The signature move is the live equalizer paired with the cover as the room's only light source. Recent plays form a shelf below, not a data table.

**Constraints:** Discord only accepts online image URLs; the app never controls playback, so no transport controls, progress bar, or fake queue. Spanish copy. Native Windows title bar, keyboard focus, 4.5:1 body contrast.

## Direction contract

THESIS: The product opens as a now-playing screen, not a settings dialog; it refuses the form-plus-cards utility default.

OWN-WORLD: Ink-green ground (`#050A08`), aquamarine `#6FFFE4` reserved for live state and primary action, off-white type, 1px hairline borders, rounded album covers, Bahnschrift display over Segoe UI. No glass, gradients, neon glows or hard offset shadows.

STORY: The user sees the current track and cover at a glance, understands whether it is live or the last scrobble, can pin a different cover in place, and reaches settings with one gear.

FIRST VIEWPORT: 56px top bar with logo, wordmark, refresh and gear; a 320px cover on the left; status, title, artist, album, equalizer, three 72px cover-source tiles and the save/remove row on the right; a five-cover recent shelf along the bottom with a footer naming Last.fm as the source.

FORM: Pinned by the brief (music player), not rolled. seed:6233ad1f9de8389a

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
