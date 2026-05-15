"""
Config loader for auditerm.
Reads ~/.config/auditerm/config (INI-style).

Config format:

[app]
start_dir = /home/alice
volume    = 75          # 0-100

[theme]
border       = red
title        = white
text         = white
muted        = blue
highlight    = black
highlight_bg = cyan
status       = red
warning      = yellow
error        = red
visualizer   = cyan

[visualizer]
style    = bars         # bars | mirror | wave | dots | off
bars     = 40           # number of frequency bars (overridden by terminal width)
height   = 8            # rows tall
fps      = 20
gain     = 14.0
gravity  = 0.035
smoothing= 0.75
monstercat = 1.8
peak_mode = rms         # rms | peak (how to normalize FFT bands)

[browser]
show_hidden = false
sort        = name      # name | ext | size

[ui]
default_panel  = split  # split | browser | library
show_help_bar  = true
progress_style = bar    # bar | dots | minimal
title_art      = true
unicode_icons  = true
border_style   = single # single | double | rounded | ascii

[keybinds]
quit         = q
stop         = s
next         = >
prev         = <
volume_up    = +
volume_down  = -
browser      = b
library      = l
visualizer   = v
add_to_album = a
new_album    = n
"""

from __future__ import annotations
import configparser
from pathlib import Path

CONFIG_DIR  = Path.home() / ".config" / "auditerm"
CONFIG_FILE = CONFIG_DIR / "config"

DEFAULTS: dict[str, dict[str, str]] = {
    "app": {
        "start_dir": str(Path.home() / "Music"),
        "volume":    "80",
    },
    "theme": {
        "border":       "cyan",
        "title":        "cyan",
        "text":         "white",
        "muted":        "white",
        "highlight":    "black",
        "highlight_bg": "cyan",
        "status":       "green",
        "warning":      "yellow",
        "error":        "red",
        "visualizer":   "cyan",
        "visualizer2":  "green",   # peak dot color
        "playing":      "green",
        "bar_empty":    "white",
    },
    "visualizer": {
        "style":       "bars",
        "bars":        "40",
        "height":      "8",
        "fps":         "20",
        "gain":        "14.0",
        "gravity":     "0.035",
        "smoothing":   "0.75",
        "monstercat":  "1.8",
        "peak_mode":   "rms",
    },
    "browser": {
        "show_hidden": "false",
        "sort":        "name",
    },
    "ui": {
        "default_panel":   "split",
        "show_help_bar":   "true",
        "progress_style":  "bar",
        "title_art":       "true",
        "unicode_icons":   "true",
        "border_style":    "single",
    },
    "keybinds": {
        "quit":         "q",
        "stop":         "s",
        "next":         ">",
        "prev":         "<",
        "volume_up":    "+",
        "volume_down":  "-",
        "browser":      "b",
        "library":      "l",
        "visualizer":   "v",
        "add_to_album": "a",
        "new_album":    "n",
        "search":       "/",
        "help":         "?",
    },
}


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
        return curses.COLOR_WHITE


class Config:
    def __init__(self):
        self._parser = configparser.ConfigParser(
            interpolation=None,
            comment_prefixes=("#", ";"),
            inline_comment_prefixes=("#",),
        )
        self._load()

    def _load(self):
        self._parser.read_dict(DEFAULTS)
        if CONFIG_FILE.exists():
            try:
                self._parser.read(str(CONFIG_FILE), encoding="utf-8")
            except configparser.Error:
                pass

    def reload(self):
        self._load()

    # ── generic accessors ─────────────────────────────────────────

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

    def set(self, section: str, key: str, value: str):
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, value)

    # ── theme/color helpers ───────────────────────────────────────
    # These map the [theme] key names to what colors.py expects.

    def color(self, key: str) -> int:
        """
        key is one of the old [colors] names used internally.
        We map them to [theme] keys from the user's config.
        """
        _THEME_MAP = {
            # internal key      → [theme] key
            "bg":           ("theme", "text",         "black"),
            "fg":           ("theme", "text",         "white"),
            "accent":       ("theme", "visualizer",   "cyan"),
            "accent2":      ("theme", "visualizer2",  "green"),
            "border":       ("theme", "border",       "cyan"),
            "selected_bg":  ("theme", "highlight_bg", "cyan"),
            "selected_fg":  ("theme", "highlight",    "black"),
            "playing_fg":   ("theme", "playing",      "green"),
            "muted":        ("theme", "muted",        "white"),
            "error":        ("theme", "error",        "red"),
            "title_fg":     ("theme", "title",        "cyan"),
            "status_fg":    ("theme", "status",       "green"),
            "bar_filled":   ("theme", "visualizer",   "cyan"),
            "bar_empty":    ("theme", "bar_empty",    "white"),
        }
        if key in _THEME_MAP:
            section, theme_key, default = _THEME_MAP[key]
            name = self.get(section, theme_key, default) or default
        else:
            name = self.get("theme", key, "white") or "white"
        return _name_to_curses(name)

    # ── convenience: old-style section getters ────────────────────
    # These let the rest of the code use cfg.get("ui", ...) etc.
    # but also transparently read from [app] / [theme] / [browser].

    @property
    def music_dir(self) -> str:
        d = self.get("app", "start_dir", str(Path.home() / "Music")) or ""
        p = Path(d).expanduser()
        return str(p) if p.exists() else str(Path.home())

    @property
    def start_volume(self) -> float:
        v = self.getint("app", "volume", 80)
        return max(0, min(100, v)) / 100.0

    def write_default(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(_DEFAULT_CONFIG_TEXT, encoding="utf-8")


_DEFAULT_CONFIG_TEXT = """\
# auditerm configuration
# ~/.config/auditerm/config

[app]
start_dir = ~/Music
volume    = 80          # 0-100

[theme]
border       = cyan
title        = cyan
text         = white
muted        = white
highlight    = black
highlight_bg = cyan
status       = green
warning      = yellow
error        = red
visualizer   = cyan     # bar fill color
visualizer2  = green    # peak dot color
playing      = green

[visualizer]
style      = bars       # bars | mirror | wave | dots | off
height     = 8          # rows tall
fps        = 20
gain       = 14.0       # raise if bars look flat
gravity    = 0.035      # fall speed (lower = floatier)
smoothing  = 0.75       # rise smoothing
monstercat = 1.8        # lateral flow between bars
peak_mode  = rms        # rms | peak

[browser]
show_hidden = false
sort        = name      # name | ext | size

[ui]
default_panel  = split  # split | browser | library
show_help_bar  = true
progress_style = bar    # bar | dots | minimal
title_art      = true
unicode_icons  = true
border_style   = single # single | double | rounded | ascii

[keybinds]
quit         = q
stop         = s
next         = >
prev         = <
volume_up    = +
volume_down  = -
browser      = b
library      = l
visualizer   = v
add_to_album = a
new_album    = n
"""
