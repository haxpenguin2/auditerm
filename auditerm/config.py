"""
Config loader for auditerm.
Reads ~/.config/auditerm/config (INI-style).
"""

from __future__ import annotations
import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "auditerm"
CONFIG_FILE = CONFIG_DIR / "config"

DEFAULTS: dict[str, dict[str, str]] = {
    "general": {
        "music_dir":     str(Path.home() / "Music"),
        "remember_last": "true",
        "last_path":     "",
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
        "style":       "bars",
        "height":      "8",
        "fps":         "20",
        "gain":        "14.0",
        "gravity":     "0.035",
        "smoothing":   "0.75",
        "monstercat":  "1.8",
    },
    "ui": {
        "default_panel":    "split",
        "show_help_bar":    "true",
        "show_status_bar":  "true",
        "progress_style":   "bar",
        "time_format":      "elapsed",
        "title_art":        "true",
        "unicode_icons":    "true",
        "border_style":     "single",
    },
    "keybinds": {
        "quit":         "q",
        "play_pause":   " ",
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
        # Step 1: load hardcoded defaults
        self._parser.read_dict(DEFAULTS)
        # Step 2: overlay user file on top — only keys present in the
        # file will change; everything else keeps its default value
        if CONFIG_FILE.exists():
            try:
                self._parser.read(str(CONFIG_FILE), encoding="utf-8")
            except configparser.Error:
                pass

    def reload(self):
        self._load()

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
        name = self.get("colors", key, "white") or "white"
        return _name_to_curses(name)

    def set(self, section: str, key: str, value: str):
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, value)

    def write_default(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(_DEFAULT_CONFIG_TEXT, encoding="utf-8")


_DEFAULT_CONFIG_TEXT = """\
# auditerm configuration
# ~/.config/auditerm/config
# Uncomment any line to override the default.

[general]
# music_dir     = ~/Music

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
# height        = 8
# fps           = 20
# gain          = 14.0        # raise if bars look flat
# gravity       = 0.035       # fall speed
# smoothing     = 0.75        # rise smoothing
# monstercat    = 1.8         # lateral flow between bars

[ui]
# default_panel  = split      # split | browser | library
# show_help_bar  = true
# progress_style = bar        # bar | dots | minimal
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
"""
