"""Shared visual language for LastfmPresence.

The world is sampled from the app icon: an aquamarine disc (#6FFFE4) with
black line art. Aquamarine is reserved for live state and primary action;
the ground is an ink-green listening room.
"""

from __future__ import annotations

import math
import sys
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import httpx
from PIL import Image, ImageDraw, ImageOps

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Palette ------------------------------------------------------------------
ACCENT = "#6FFFE4"
ACCENT_DEEP = "#2ED9C0"
ACCENT_INK = "#04211C"

INK = "#050A08"
PANEL = "#0B1310"
ELEVATED = "#0F1A15"
HOVER = "#12241F"

PAPER = "#EAFBF5"
LABEL = "#A9C4BA"
MUTED = "#7E9A90"
DIM = "#5C746C"  # non-text only (separators, resting icon strokes)

BORDER = "#182A24"
BORDER_STRONG = "#28443B"

ERROR = "#FF8A7A"
WARNING = "#FFC46B"
SUCCESS = ACCENT

# Type ---------------------------------------------------------------------
FONT_DISPLAY = "Bahnschrift"
FONT_BODY = "Segoe UI"


# Assets -------------------------------------------------------------------
def assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
        if (base_dir / "src" / "presentation" / "gui" / "assets").exists():
            return base_dir / "src" / "presentation" / "gui" / "assets"
        if (base_dir / "assets").exists():
            return base_dir / "assets"
    return Path(__file__).parent / "assets"


def app_icon_pil(size: int = 64) -> Optional[Image.Image]:
    path = assets_dir() / "icon.ico"
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return None


def set_window_icon(window) -> None:
    path = assets_dir() / "icon.ico"
    if not path.exists():
        return
    try:
        window.iconbitmap(str(path))
    except Exception:
        pass


def font(size: int, weight: str = "normal", display: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(
        family=FONT_DISPLAY if display else FONT_BODY,
        size=size,
        weight=weight,
    )


def pil_to_ctk(image: Image.Image, size: Optional[tuple[int, int]] = None) -> ctk.CTkImage:
    if size:
        image = image.resize(size, Image.LANCZOS)
    return ctk.CTkImage(light_image=image, dark_image=image, size=image.size)


# Icons --------------------------------------------------------------------
_ICON_PIL_CACHE: dict[tuple[str, int, str], Image.Image] = {}


def _draw_icon(name: str, scale: int, color: str) -> Image.Image:
    s = 64 * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(s * 0.052))

    if name == "gear":
        c = s / 2
        body = s * 0.29
        outer = s * 0.42
        tooth_width = max(2, int(s * 0.13))
        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([c - body, c - body, c + body, c + body], fill=255)
        for i in range(8):
            a = math.radians(i * 45)
            md.line(
                [
                    c + math.cos(a) * (body - s * 0.03),
                    c + math.sin(a) * (body - s * 0.03),
                    c + math.cos(a) * outer,
                    c + math.sin(a) * outer,
                ],
                fill=255,
                width=tooth_width,
            )
        hub = s * 0.105
        md.ellipse([c - hub, c - hub, c + hub, c + hub], fill=0)
        solid = Image.new("RGBA", (s, s), color)
        img = Image.composite(solid, img, mask)

    elif name == "refresh":
        box = [s * 0.17, s * 0.17, s * 0.83, s * 0.83]
        d.arc(box, start=35, end=300, fill=color, width=w)
        d.polygon(
            [(s * 0.79, s * 0.13), (s * 0.84, s * 0.34), (s * 0.63, s * 0.28)],
            fill=color,
        )

    elif name == "external":
        d.rounded_rectangle(
            [s * 0.16, s * 0.27, s * 0.67, s * 0.80],
            radius=s * 0.07,
            outline=color,
            width=w,
        )
        d.line([s * 0.42, s * 0.58, s * 0.81, s * 0.19], fill=color, width=w)
        d.line([s * 0.58, s * 0.19, s * 0.81, s * 0.19], fill=color, width=w)
        d.line([s * 0.81, s * 0.19, s * 0.81, s * 0.42], fill=color, width=w)

    elif name == "close":
        d.line([s * 0.27, s * 0.27, s * 0.73, s * 0.73], fill=color, width=w)
        d.line([s * 0.73, s * 0.27, s * 0.27, s * 0.73], fill=color, width=w)

    elif name == "check":
        d.line(
            [(s * 0.22, s * 0.53), (s * 0.42, s * 0.72), (s * 0.79, s * 0.29)],
            fill=color,
            width=w,
            joint="curve",
        )

    elif name == "chevron":
        d.line(
            [(s * 0.39, s * 0.24), (s * 0.64, s * 0.50), (s * 0.39, s * 0.76)],
            fill=color,
            width=w,
            joint="curve",
        )

    elif name == "note":
        d.ellipse([s * 0.20, s * 0.55, s * 0.42, s * 0.77], fill=color)
        d.line([s * 0.41, s * 0.66, s * 0.41, s * 0.24], fill=color, width=w)
        d.line([s * 0.41, s * 0.24, s * 0.70, s * 0.18], fill=color, width=w)
        d.line([s * 0.70, s * 0.18, s * 0.70, s * 0.58], fill=color, width=w)
        d.ellipse([s * 0.51, s * 0.48, s * 0.71, s * 0.60], fill=color)

    return img


def icon(name: str, size: int = 18, color: str = ACCENT) -> ctk.CTkImage:
    key = (name, size, color)
    pil = _ICON_PIL_CACHE.get(key)
    if pil is None:
        pil = _draw_icon(name, 4, color).resize((size * 4, size * 4), Image.LANCZOS)
        _ICON_PIL_CACHE[key] = pil
    return pil_to_ctk(pil, (size, size))


# Cover images -------------------------------------------------------------
_IMAGE_CACHE: "OrderedDict[str, Image.Image]" = OrderedDict()
_IMAGE_LOCK = threading.Lock()
_PLACEHOLDER_CACHE: dict[int, Image.Image] = {}


def _placeholder(size: int) -> Image.Image:
    cached = _PLACEHOLDER_CACHE.get(size)
    if cached is not None:
        return cached

    s = 600
    img = Image.new("RGB", (s, s), PANEL)
    d = ImageDraw.Draw(img)
    c = s / 2
    radius = s * 0.40
    d.ellipse(
        [c - radius, c - radius, c + radius, c + radius],
        fill=ELEVATED,
        outline=BORDER_STRONG,
        width=3,
    )
    for r in range(int(radius) - 34, int(radius * 0.42), -26):
        d.ellipse([c - r, c - r, c + r, c + r], outline="#14211C", width=2)
    d.ellipse(
        [c - s * 0.14, c - s * 0.14, c + s * 0.14, c + s * 0.14],
        fill=ACCENT,
    )
    d.ellipse(
        [c - s * 0.018, c - s * 0.018, c + s * 0.018, c + s * 0.018],
        fill=INK,
    )
    d.arc(
        [c - radius + 14, c - radius + 14, c + radius - 14, c + radius - 14],
        start=200,
        end=258,
        fill="#22352E",
        width=5,
    )
    out = img.resize((size, size), Image.LANCZOS)
    _PLACEHOLDER_CACHE[size] = out
    return out


def load_pil_image(source: str, timeout: float = 8.0) -> Optional[Image.Image]:
    """Read a cover from an http(s) URL or a local path. Safe to call off-thread."""
    if not source:
        return None
    with _IMAGE_LOCK:
        cached = _IMAGE_CACHE.get(source)
        if cached is not None:
            _IMAGE_CACHE.move_to_end(source)
            return cached

    try:
        if source.startswith(("http://", "https://")):
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(source)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
        else:
            path = Path(source)
            if not path.exists():
                return None
            image = Image.open(path).convert("RGB")
    except Exception:
        return None

    with _IMAGE_LOCK:
        _IMAGE_CACHE[source] = image
        _IMAGE_CACHE.move_to_end(source)
        while len(_IMAGE_CACHE) > 60:
            _IMAGE_CACHE.popitem(last=False)
    return image


def square_cover(image: Optional[Image.Image], size: int, radius: int = 10) -> Image.Image:
    """Fit to a square and round the corners. Returns RGBA at `size`."""
    if image is None:
        base = _placeholder(size).convert("RGBA")
    else:
        base = ImageOps.fit(image, (size, size), method=Image.LANCZOS).convert("RGBA")

    if radius <= 0:
        return base

    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size * 4 - 1, size * 4 - 1],
        radius=radius * 4,
        fill=255,
    )
    mask = mask.resize((size, size), Image.LANCZOS)
    base.putalpha(mask)
    return base


def cover_image(source: str, size: int, radius: int = 10) -> ctk.CTkImage:
    return pil_to_ctk(square_cover(load_pil_image(source), size, radius), (size, size))


def placeholder_image(size: int, radius: int = 10) -> ctk.CTkImage:
    return pil_to_ctk(square_cover(None, size, radius), (size, size))


# Time ---------------------------------------------------------------------
def format_relative_time(timestamp: Optional[int]) -> str:
    if not timestamp:
        return ""
    try:
        then = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return ""
    seconds = max(0, int((datetime.now(timezone.utc) - then).total_seconds()))
    if seconds < 60:
        return "hace un momento"
    minutes = seconds // 60
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} h"
    days = hours // 24
    return f"hace {days} d"
