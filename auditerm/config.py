"""
Config loader for auditerm.
Reads ~/.config/auditerm/config (INI-style).
All keys are optional; defaults are used when missing.
"""

import os
import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "auditerm"
CONFIG_FILE = CONFIG_DIR / "config"

DEFAULTS = {
    "general": {
        "music_dir": str(Path.home() / "Music"),
        "remember_last": "true",
        "last_path": "",
    },
    "colors": {
        # dark utilitarian palette — all are curses color indices 0-7
        # or named: black, red, green, yellow, blue, magenta, cyan, white
        "bg":              "black",
        "fg":              "white",
        "accent":          "cyan",
        "accent2":         "green",
        "border":          "cyan",
        "selected_bg":     "cyan",
        "selected_fg":     "black",
        "playing_fg":      "green",
        "muted":           "white",      # dim/muted text
        "error":           "red",
        "title_fg":        "cyan",
        "status_fg":       "green",
        "bar_filled":      "cyan",
        "bar_empty":       "white",
    },
    "visualizer": {
        # styles: bars | wave | spectrum | dots | off
        "style":           "bars",
        "height":          "8",
        "bar_char":        "█",
        "bar_empty_char":  "░",
        "wave_char":       "•",
        "mirror":          "true",       # mirror bars left+right
        "color":           "cyan",
        "color_peak":      "green",
        "fps":             "20",
    },
    "ui": {
        # layout: split | browser | library
        "default_panel":   "split",
        "show_help_bar":   "true",
        "show_status_bar": "true",
        "progress_style":  "bar",        # bar | dots | minimal
        "time_format":     "elapsed",    # elapsed | remaining
        "title_art":       "true",       # show ASCII title on home
        "unicode_icons":   "true",       # use  ▶ ⏸ etc.
        "border_style":    "single",     # single | double | rounded | ascii
    },
    "keybinds": {
        "quit":            "q",
        "play_pause":      " ",
        "stop":            "s",
        "next":            ">",
        "prev":            "<",
        "volume_up":       "+",
        "volume_down":     "-",
        "toggle_panel":    "Tab",
        "browser":         "b",
        "library":         "l",
        "visualizer":      "v",
        "add_to_album":    "a",
        "new_album":       "n",
        "search":          "/",
        "help":            "?",
    },
}


def _name_to_curses(name: str) -> int:
    import curses
    mapping = {
        "black":   curses.COLOR_BLACK,
        "red":     curses.COLOR_RED,
        "green":   curses.COLOR_GREEN,
        "yellow":  curses.COLOR_YELLOW,
        "blue":    curses.COLOR_BLUE,
        "magenta": curses.COLOR_MAGENTA,
        "cyan":    curses.COLOR_CYAN,
        "white":   curses.COLOR_WHITE,
    }

    try:
        name_lower = name.lower()
        # Check if the name is in our dictionary first
        if name_lower in mapping:
            return mapping[name_lower]

        # Only try to cast to an integer if it wasn't a recognized string
        return int(name)
    except (ValueError, AttributeError):
        return curses.COLOR_WHITE

class Config:
    def __init__(self):
        self._parser = configparser.ConfigParser()
        self._load()

    def _load(self):
        # Set defaults
        for section, values in DEFAULTS.items():
            self._parser[section] = values

        if CONFIG_FILE.exists():
            self._parser.read(CONFIG_FILE)

    def get(self, section: str, key: str, fallback=None):
        try:
            return self._parser.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def getint(self, section: str, key: str, fallback=0):
        try:
            return self._parser.getint(section, key)
        except Exception:
            return fallback

    def getbool(self, section: str, key: str, fallback=False):
        try:
            return self._parser.getboolean(section, key)
        except Exception:
            return fallback

    def color(self, key: str) -> int:
        name = self.get("colors", key, "white")
        return _name_to_curses(name)

    def write_default(self):
        """Write a default config file if none exists."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            with open(CONFIG_FILE, "w") as f:
                f.write(_DEFAULT_CONFIG_TEXT)


_DEFAULT_CONFIG_TEXT = """\
# auditerm configuration file
# ~/.config/auditerm/config
#
# All values shown are defaults. Uncomment and change to override.

[general]
# music_dir = ~/Music
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
# style         = bars       # bars | wave | spectrum | dots | off
# height        = 8
# bar_char      = █
# bar_empty_char= ░
# mirror        = true
# color         = cyan
# color_peak    = green
# fps           = 20

[ui]
# default_panel = split      # split | browser | library
# show_help_bar = true
# show_status_bar = true
# progress_style = bar       # bar | dots | minimal
# time_format   = elapsed    # elapsed | remaining
# title_art     = true
# unicode_icons = true
# border_style  = single     # single | double | rounded | ascii

[keybinds]
# quit          = q
# play_pause    = (space)
# stop          = s
# next          = >
# prev          =
# volume_up     = +
# volume_down   = -
# toggle_panel  = Tab
# browser       = b
# library       = l
# visualizer    = v
# add_to_album  = a
# new_album     = n
# search        = /
# help          = ?
"""
