"""
TUI file browser panel.
Navigates the filesystem; Enter plays a file or enters a directory.
"""

from __future__ import annotations

import curses
from pathlib import Path

from auditerm.config import Config
from auditerm.ui.colors import (
    PAIR_ACCENT,
    PAIR_BORDER,
    PAIR_DEFAULT,
    PAIR_HEADER,
    PAIR_MUTED,
    PAIR_PLAYING,
    PAIR_SELECTED,
    cp,
)

AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus", ".wma", ".aiff"}


def _border_chars(cfg: Config):
    """
    Return curses-safe border characters.

    Unicode border glyphs can overflow in some curses builds, so this uses ACS
    line-drawing chars when possible and falls back to ASCII.
    """
    style = cfg.get("ui", "border_style", "single").lower()

    if style == "ascii":
        return (
            ord("|"), ord("|"),
            ord("-"), ord("-"),
            ord("+"), ord("+"),
            ord("+"), ord("+"),
        )

    # curses ACS constants are safe chtype values on normal terminals
    v = getattr(curses, "ACS_VLINE", ord("|"))
    h = getattr(curses, "ACS_HLINE", ord("-"))
    tl = getattr(curses, "ACS_ULCORNER", ord("+"))
    tr = getattr(curses, "ACS_URCORNER", ord("+"))
    bl = getattr(curses, "ACS_LLCORNER", ord("+"))
    br = getattr(curses, "ACS_LRCORNER", ord("+"))

    # rounded/double/single all use safe line-drawing chars here
    return (v, v, h, h, tl, tr, bl, br)


class FileBrowser:
    def __init__(self, cfg: Config, start_dir: str | None = None):
        self.cfg = cfg
        root = start_dir or cfg.get("general", "music_dir", str(Path.home()))
        self.cwd = Path(root).expanduser()
        if not self.cwd.exists() or not self.cwd.is_dir():
            self.cwd = Path.home()

        self.entries: list[Path] = []
        self.cursor = 0
        self.scroll = 0
        self.on_play = None        # callback(path: str)
        self.on_queue_dir = None   # callback(paths: list[str])
        self._refresh()

    def _refresh(self):
        try:
            entries = sorted(self.cwd.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            self.entries = [p for p in entries if not p.name.startswith(".")]
        except (PermissionError, FileNotFoundError, OSError):
            self.entries = []

        if self.entries:
            self.cursor = min(self.cursor, len(self.entries) - 1)
        else:
            self.cursor = 0
        self.scroll = 0

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        if h < 3 or w < 10:
            return

        bc = _border_chars(self.cfg)

        # border
        try:
            win.attron(cp(PAIR_BORDER))
            win.border(*bc)
            win.attroff(cp(PAIR_BORDER))
        except curses.error:
            pass

        # header
        cwd_str = str(self.cwd)
        title = f" 📁 {cwd_str} "
        max_title = max(0, w - 4)
        if len(title) > max_title and max_title > 6:
            title = " …" + cwd_str[-(max_title - 4):] + " "
        elif len(title) > max_title:
            title = title[:max_title]

        try:
            win.attron(cp(PAIR_HEADER) | curses.A_BOLD)
            win.addstr(0, 2, title[:max_title])
            win.attroff(cp(PAIR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        # entries
        visible = max(0, h - 2)
        if self.cursor >= self.scroll + visible:
            self.scroll = self.cursor - visible + 1
        if self.cursor < self.scroll:
            self.scroll = self.cursor

        for i in range(visible):
            idx = i + self.scroll
            if idx >= len(self.entries):
                break

            entry = self.entries[idx]
            row = i + 1
            is_dir = entry.is_dir()
            is_audio = entry.suffix.lower() in AUDIO_EXTS
            is_cur = idx == self.cursor

            icon = "▸ " if is_dir else ("♪ " if is_audio else "  ")
            name = entry.name + ("/" if is_dir else "")
            line = f" {icon}{name}"

            max_line = max(0, w - 2)
            if len(line) > max_line and max_line > 1:
                line = line[: max_line - 1] + "…"
            else:
                line = line[:max_line]

            if is_cur:
                attr = cp(PAIR_SELECTED) | curses.A_BOLD
            elif is_dir:
                attr = cp(PAIR_ACCENT) | curses.A_BOLD
            elif is_audio:
                attr = cp(PAIR_PLAYING)
            else:
                attr = cp(PAIR_DEFAULT)

            try:
                win.addstr(row, 1, line.ljust(max_line)[:max_line], attr)
            except curses.error:
                pass

        # footer
        footer = " ↑↓ navigate | Enter open/play | Backspace up | h/j/k/l nav "
        try:
            win.attron(cp(PAIR_MUTED))
            win.addstr(h - 1, 2, footer[: max(0, w - 3)])
            win.attroff(cp(PAIR_MUTED))
        except curses.error:
            pass

    def handle_key(self, key) -> str | None:
        """Returns action string or None."""
        if key in (curses.KEY_UP, ord("k")):
            if self.cursor > 0:
                self.cursor -= 1

        elif key in (curses.KEY_DOWN, ord("j")):
            if self.cursor < len(self.entries) - 1:
                self.cursor += 1

        elif key in (curses.KEY_ENTER, 10, 13):
            if not self.entries:
                return None

            entry = self.entries[self.cursor]
            if entry.is_dir():
                self.cwd = entry
                self.cursor = 0
                self.scroll = 0
                self._refresh()
                return "cd"

            if entry.suffix.lower() in AUDIO_EXTS:
                if self.on_play:
                    self.on_play(str(entry))
                return "play"

        elif key in (curses.KEY_BACKSPACE, 127, 8, ord("h")):
            parent = self.cwd.parent
            if parent != self.cwd:
                self.cwd = parent
                self.cursor = 0
                self.scroll = 0
                self._refresh()
                return "up"

        elif key == curses.KEY_PPAGE:
            self.cursor = max(0, self.cursor - 10)

        elif key == curses.KEY_NPAGE:
            self.cursor = min(max(0, len(self.entries) - 1), self.cursor + 10)

        elif key in (curses.KEY_HOME, ord("g")):
            self.cursor = 0

        elif key in (curses.KEY_END, ord("G")):
            self.cursor = max(0, len(self.entries) - 1)

        return None

    def current_path(self) -> Path | None:
        if self.entries and 0 <= self.cursor < len(self.entries):
            return self.entries[self.cursor]
        return None
