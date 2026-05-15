"""
Config loader for auditerm.
Reads ~/.config/auditerm/config (INI-style).
All keys are optional; defaults are used when missing.

Fix vs previous version:
  - configparser.read_dict() used for defaults so they can't be
    silently dropped by a malformed user file
  - _name_to_curses moved here (was imported back from here by colors.py,
    causing a circular-ish dependency)
  - write_default() now always writes all sections so users see every option
"""

from __future__ import annotations

import configparser
from pathlib import Path

CONFIG_DIR  = Path.home() / ".config" / "auditerm"
CONFIG_FILE = CONFIG_DIR / "config"

# ── Defaults ──────────────────────────────────────────────────────────────────
# Every key that auditerm reads must appear here.
# These are loaded first; the user's config file is then merged on top,
# so missing user keys always fall back to these values.

DEFAULTS: dict[str, dict[str, str]] = {
    "general": {
        "music_dir":    str(Path.home() / "Music"),
        "remember_last": "true",
        "last_path":    "",
    },
    "colors": {
        "bg":          "black",
        "fg":          "white",
        "accent":      "cyan",
        "accent2":     "green",
        "border":      "cyan",
        "selected_bg": "cyan",
        "selected_fg": "black",
        "playing_fg":  "green",
        "muted":       "white",
        "error":       "red",
        "title_fg":    "cyan",
        "status_fg":   "green",
        "bar_filled":  "cyan",
        "bar_empty":   "white",
    },
    "visualizer": {
        "style":          "bars",   # bars | mirror | wave | dots | off
        "height":         "8",
        "fps":            "20",
        "gain":           "14.0",
        "gravity":        "0.035",
        "smoothing":      "0.75",
        "monstercat":     "1.8",
    },
    "ui": {
        "default_panel":   "split",   # split | browser | library
        "show_help_bar":   "true",
        "show_status_bar": "true",
        "progress_style":  "bar",     # bar | dots | minimal
        "time_format":     "elapsed", # elapsed | remaining
        "title_art":       "true",
        "unicode_icons":   "true",
        "border_style":    "single",  # single | double | rounded | ascii
    },
    "keybinds": {
        "quit":        "q",
        "play_pause":  " ",
        "stop":        "s",
        "next":        ">",
        "prev":        "<",
        "volume_up":   "+",
        "volume_down": "-",
        "browser":     "b",
        "library":     "l",
        "visualizer":  "v",
        "add_to_album": "a",
        "new_album":   "n",
        "search":      "/",
        "help":        "?",
    },
}

# ── Color name → curses int ───────────────────────────────────────────────────

def _name_to_curses(name: str) -> int:
    import curses
    _MAP = {
        "black":   curses.COLOR_BLACK,
        "red":     curses.COLOR_RED,
        "green":   curses.COLOR_GREEN,
        "yellow":  curses.COLOR_YELLOW,
        "blue":    curses.COLOR_BLUE,
        "magenta": curses.COLOR_MAGENTA,
        "cyan":    curses.COLOR_CYAN,
        "white":   curses.COLOR_WHITE,
    }
    name = (name or "white").strip().lower()
    if name in _MAP:
        return _MAP[name]
    try:
        return int(name)
    except ValueError:
        import curses as _c
        return _c.COLOR_WHITE


# ── Config class ──────────────────────────────────────────────────────────────

class Config:
    def __init__(self):
        self._parser = configparser.ConfigParser(
            interpolation=None,   # don't interpret % in values
            comment_prefixes=("#", ";"),
            inline_comment_prefixes=("#",),
        )
        self._load()

    def _load(self):
        # 1. Seed every section+key with the hardcoded defaults
        self._parser.read_dict(DEFAULTS)

        # 2. Overlay the user's file — only the keys they set will change
        if CONFIG_FILE.exists():
            try:
                self._parser.read(CONFIG_FILE, encoding="utf-8")
            except configparser.Error:
                pass  # bad file → just use defaults

    def reload(self):
        """Re-read the config file without restarting."""
        self._load()

    # ── Accessors ─────────────────────────────────────────────────

    def get(self, section: str, key: str, fallback: str | None = None) -> str | None:
        try:
            return self._parser.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        try:
            return self._parser.getint(section, key)
        except Exception:
            return fallback

    def getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        try:
            return self._parser.getfloat(section, key)
        except Exception:
            return fallback

    def getbool(self, section: str, key: str, fallback: bool = False) -> bool:
        try:
            return self._parser.getboolean(section, key)
        except Exception:
            return fallback

    def color(self, key: str) -> int:
        """Return a curses color integer for a color name from [colors]."""
        name = self.get("colors", key, "white") or "white"
        return _name_to_curses(name)

    def set(self, section: str, key: str, value: str):
        """Set a value at runtime (does not persist to disk)."""
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, value)

    # ── Default config file ───────────────────────────────────────

    def write_default(self):
        """Write the default config file if it doesn't exist yet."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(_DEFAULT_CONFIG_TEXT, encoding="utf-8")


_DEFAULT_CONFIG_TEXT = """\
# auditerm configuration
# ~/.config/auditerm/config
#
# Uncomment and edit any line to override the default.
# Run auditerm after saving — changes take effect on next launch.
# (press [r] inside auditerm to reload without restarting — coming soon)

[general]
# music_dir     = ~/Music
# remember_last = true

[colors]
# bg            = black
# fg            = white
# accent        = cyan
# accent2       = green
# border        = cyan
# selected_bg   = cyan
# selected_fg   = black
# playing_fg    = green
# muted         = white
# error         = red
# title_fg      = cyan
# status_fg     = green
# bar_filled    = cyan
# bar_empty     = white

[visualizer]
# style         = bars        # bars | mirror | wave | dots | off
# height        = 8           # rows tall the visualizer panel is
# fps           = 20          # draw rate
# gain          = 14.0        # raise if bars look flat
# gravity       = 0.035       # fall speed (lower = floatier)
# smoothing     = 0.75        # rise smoothing (higher = slower attack)
# monstercat    = 1.8         # lateral flow between bars (higher = smoother)

[ui]
# default_panel  = split      # split | browser | library
# show_help_bar  = true
# show_status_bar= true
# progress_style = bar        # bar | dots | minimal
# time_format    = elapsed    # elapsed | remaining
# title_art      = true
# unicode_icons  = true
# border_style   = single     # single | double | rounded | ascii

[keybinds]
# quit           = q
# stop           = s
# next           = >
# prev           = <
# volume_up      = +
# volume_down    = -
# browser        = b
# library        = l
# visualizer     = v
# add_to_album   = a
# new_album      = n
# search         = /
# help           = ?
"""
