"""
TUI file browser panel.
Navigates the filesystem; Enter plays a file or enters a directory.
"""

import curses
import os
from pathlib import Path
from auditerm.ui.colors import cp, PAIR_ACCENT, PAIR_SELECTED, PAIR_MUTED, PAIR_DEFAULT, PAIR_PLAYING, PAIR_BORDER, PAIR_HEADER
from auditerm.config import Config

AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus", ".wma", ".aiff"}

BORDER_CHARS = {
    "single":  ("┌","─","┐","│","└","┘","├","┤","┬","┴","┼"),
    "double":  ("╔","═","╗","║","╚","╝","╠","╣","╦","╩","╬"),
    "rounded": ("╭","─","╮","│","╰","╯","├","┤","┬","┴","┼"),
    "ascii":   ("+","-","+","|","+","+","+","+","+","+","+"),
}


def _border(cfg: Config):
    s = cfg.get("ui", "border_style", "single")
    return BORDER_CHARS.get(s, BORDER_CHARS["single"])


class FileBrowser:
    def __init__(self, cfg: Config, start_dir: str | None = None):
        self.cfg = cfg
        self.cwd = Path(start_dir or cfg.get("general", "music_dir", str(Path.home()))).expanduser()
        if not self.cwd.exists():
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
        except PermissionError:
            self.entries = []
        self.cursor = min(self.cursor, max(0, len(self.entries) - 1))
        self.scroll = 0

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()
        bc = _border(self.cfg)

        # ── border ───────────────────────────────────────────────
        try:
            win.attron(cp(PAIR_BORDER))
            win.border(bc[3], bc[3], bc[1], bc[1], bc[0], bc[2], bc[4], bc[5])
            win.attroff(cp(PAIR_BORDER))
        except curses.error:
            pass

        # ── header ───────────────────────────────────────────────
        title = f" 📁 {str(self.cwd)} "
        if len(title) > w - 4:
            title = " …" + str(self.cwd)[-(w - 7):] + " "
        try:
            win.attron(cp(PAIR_HEADER) | curses.A_BOLD)
            win.addstr(0, 2, title[:w - 3])
            win.attroff(cp(PAIR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        # ── entries ──────────────────────────────────────────────
        visible = h - 2
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
            name = entry.name
            if is_dir:
                name += "/"
            line = f" {icon}{name}"
            if len(line) > w - 2:
                line = line[:w - 3] + "…"

            if is_cur:
                attr = cp(PAIR_SELECTED) | curses.A_BOLD
            elif is_dir:
                attr = cp(PAIR_ACCENT) | curses.A_BOLD
            elif is_audio:
                attr = cp(PAIR_PLAYING)
            else:
                attr = cp(PAIR_MUTED)

            try:
                win.addstr(row, 1, line.ljust(w - 2)[:w - 2], attr)
            except curses.error:
                pass

        # ── footer: count ────────────────────────────────────────
        footer = f" {len(self.entries)} items | ↑↓ navigate | Enter open/play | Backspace up "
        try:
            win.attron(cp(PAIR_MUTED))
            win.addstr(h - 1, 2, footer[:w - 3])
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
                self._refresh()
                return "cd"
            elif entry.suffix.lower() in AUDIO_EXTS:
                if self.on_play:
                    self.on_play(str(entry))
                return "play"
        elif key in (curses.KEY_BACKSPACE, 127, ord("h")):
            parent = self.cwd.parent
            if parent != self.cwd:
                self.cursor = 0
                self.cwd = parent
                self._refresh()
                return "up"
        elif key == curses.KEY_PPAGE:
            self.cursor = max(0, self.cursor - 10)
        elif key == curses.KEY_NPAGE:
            self.cursor = min(len(self.entries) - 1, self.cursor + 10)
        elif key in (curses.KEY_HOME, ord("g")):
            self.cursor = 0
        elif key in (curses.KEY_END, ord("G")):
            self.cursor = max(0, len(self.entries) - 1)
        return None

    def current_path(self) -> Path | None:
        if self.entries and 0 <= self.cursor < len(self.entries):
            return self.entries[self.cursor]
        return None
