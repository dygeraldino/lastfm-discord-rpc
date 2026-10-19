# DESIGN.md — LastfmPresence "Now Spinning"

The committed visual world for the two GUI surfaces. The single source of every
value here is `src/presentation/gui/theme.py`; never hardcode a hex, font or
size outside it.

## The world

A late-night listening console. The ground is an ink-green room; the light
sources are the album cover and one reserved aquamarine that means *live*.
Nothing glows, nothing blurs, nothing gradients: hairlines, rounded covers and
typography carry the design. Aquamarine appears only where something is
actually happening: the live dot, the equalizer, a selected cover source, the
primary action.

Derived from the logo asset (`src/presentation/gui/assets/icon.ico`): an
aquamarine disc `#6FFFE4` with black line art.

## Palette — `theme.py`

| Token | Value | Use |
|---|---|---|
| `ACCENT` | `#6FFFE4` | Live state, selection ring, primary action, active count |
| `ACCENT_DEEP` | `#2ED9C0` | Hover of the primary action |
| `ACCENT_INK` | `#04211C` | Text on aquamarine fills |
| `INK` | `#050A08` | Window and section ground |
| `PANEL` | `#0B1310` | Disabled tile fill, inputs |
| `ELEVATED` | `#0F1A15` | Saved-state fill |
| `HOVER` | `#12241F` | Ghost-button hover, selected shelf tile |
| `PAPER` | `#EAFBF5` | Headlines, cover titles |
| `LABEL` | `#A9C4BA` | Secondary text, ghost-button text |
| `MUTED` | `#7E9A90` | Meta text, resting state, disabled |
| `DIM` | `#5C746C` | Non-text only (resting eq bars) |
| `BORDER` | `#182A24` | Hairlines, input and tile borders |
| `BORDER_STRONG` | `#28443B` | Resting eq bars |
| `ERROR` | `#FF8A7A` | Error copy (with text, never colour-only) |
| `WARNING` | `#FFC46B` | Reserved |

Contrast floor: `LABEL` ≥ 9:1 and `MUTED` ≥ 5:1 against `INK`; disabled tiles
run at the disabled exemption. Status is never colour-only — every dot,
ring or tint is paired with a word.

## Type

- Display: **Bahnschrift** — header wordmark 13 bold, settings title 21 bold,
  track title 30 bold, section headings 11–12 bold.
- Body: **Segoe UI** — artist 15, labels 10–12 bold, meta 8–10.

## Layout rhythm

- Outer padding 28–32px; sections separated by 1px hairlines
  (`fg_color=BORDER`, `corner_radius=0`).
- Player: 60px app bar (logo 26 + wordmark, refresh + gear right) → body
  (300px cover left radius 12; status dot 7, title, artist, album,
  92×30 equalizer, cover picker with three 64px source tiles) → recent
  shelf (six 72px covers, radius 8) → 44px footer.
- Settings: 86px header (logo 34) → form (38px entries, PANEL fill,
  1px BORDER border, focus ring turns the border `ACCENT`) → footer
  (ghost "Probar conexión", primary "Guardar cambios").
- Radii: 12 (large cover), 9–10 (buttons/shelf), 7–8 (small tiles/inputs).

## Controls

- **Primary button**: aquamarine fill, `ACCENT_INK` text, radius 8–9.
  Disabled = `PANEL` fill + `MUTED` text.
- **Ghost button**: transparent fill, 1px `BORDER` border (or none),
  `LABEL` text, `HOVER` fill on hover; icons ride left at 11–13px.
- **Source tile**: thumb radius 7; selected = 2px `ACCENT` border,
  `HOVER` fill, 9px check icon; unavailable = `INK` fill, "Sin portada",
  label `MUTED`, no cursor affordance.
- **Shelf tile**: selected = 1px `ACCENT` border over `HOVER` fill;
  whole tile clickable, `hand2` cursor.

## Icons

All drawn in code (`theme._draw_icon`): gear, refresh, external, close,
check, chevron, note. One stroke weight, cached per (name, size, colour).
No emoji inside windows; the native tray menu keeps Windows-style items.

## States (player)

`CONECTANDO` (muted) → `AHORA SUENA` (accent + equalizer) →
`ÚLTIMA REPRODUCCIÓN` (muted) → `VISTA PREVIA` (muted) → `EN ESPERA`,
`SIN CONFIGURAR`, `SIN CONEXIÓN` (`ERROR` + copy naming the recovery).
The cover picker shows only with a track selected; loading candidates
announce themselves, keep the current info, and never dead-end silently.

## Motion

One authored moment: the six equalizer bars breathe at a 90ms tick while the
track is live. Closing or `Esc` hides the player to the tray — nothing
animates on entrances.

## Assets & provenance

- Logo: `src/presentation/gui/assets/icon.ico` — tray icon, title-bar icon
  (`theme.set_window_icon`), header logos, placeholder vinyl derived from it.
- Album art: fetched from Last.fm / Deezer / MusicBrainz online URLs
  (Discord Rich Presence requirement); LRU-capped at 60 images.
- Everything else is generated code-side; no stock photos, no bundled fonts
  (Bahnschrift ships with Windows 10/11).

## Surfaces

| Surface | Mode | Note |
|---|---|---|
| `player_window.py` | Operate | Everyday surface; first thing the tray opens |
| `main_window.py` (Ajustes) | Operate | Rare; reached from the player's gear or the tray menu |
| `OverrideManager` (player footer) | Operate | Lists/removes every saved override |
