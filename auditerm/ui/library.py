"""
Library panel: shows user-defined albums and their tracks.
"""

import curses
from auditerm.library import Library, Album
from auditerm.ui.colors import cp, PAIR_ACCENT, PAIR_SELECTED, PAIR_MUTED, PAIR_DEFAULT, PAIR_PLAYING, PAIR_BORDER, PAIR_HEADER, PAIR_ACCENT2
from auditerm.config import Config


class LibraryPanel:
    def __init__(self, library: Library, cfg: Config):
        self.lib = library
        self.cfg = cfg
        self.album_cursor = 0
        self.track_cursor = 0
        self.focus = "albums"   # "albums" | "tracks"
        self.on_play = None     # callback(path)
        self.on_play_album = None  # callback(album: Album)

    def _albums(self):
        return self.lib.album_names()

    def _current_album(self) -> Album | None:
        names = self._albums()
        if names and 0 <= self.album_cursor < len(names):
            return self.lib.albums[names[self.album_cursor]]
        return None

    def draw(self, win):
        win.erase()
        h, w = win.getmaxyx()

        # split vertically: left=album list, right=track list
        half = w // 3

        try:
            win.attron(cp(PAIR_BORDER))
            win.border()
            win.attroff(cp(PAIR_BORDER))
        except curses.error:
            pass

        # ── album list ───────────────────────────────────────────
        albums = self._albums()
        alb_title = " ♫ ALBUMS "
        try:
            win.attron(cp(PAIR_HEADER) | curses.A_BOLD)
            win.addstr(0, 2, alb_title)
            win.attroff(cp(PAIR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        for i, name in enumerate(albums[:h - 2]):
            is_cur = i == self.album_cursor
            line = f"  {name}"[:half - 1]
            attr = cp(PAIR_SELECTED) | curses.A_BOLD if is_cur and self.focus == "albums" \
                   else cp(PAIR_ACCENT) if is_cur \
                   else cp(PAIR_DEFAULT)
            try:
                win.addstr(i + 1, 1, line.ljust(half - 2)[:half - 2], attr)
            except curses.error:
                pass

        if not albums:
            try:
                win.addstr(2, 2, "No albums yet.", cp(PAIR_MUTED))
                win.addstr(3, 2, "Press [n] to create one,", cp(PAIR_MUTED))
                win.addstr(4, 2, "[a] to add a file.", cp(PAIR_MUTED))
            except curses.error:
                pass

        # ── vertical divider ─────────────────────────────────────
        try:
            win.attron(cp(PAIR_BORDER))
            for row in range(1, h - 1):
                win.addch(row, half, "│")
            win.attroff(cp(PAIR_BORDER))
        except curses.error:
            pass

        # ── track list ───────────────────────────────────────────
        album = self._current_album()
        trk_title = f" {album.name} " if album else " — no album — "
        try:
            win.attron(cp(PAIR_HEADER) | curses.A_BOLD)
            win.addstr(0, half + 2, trk_title[:w - half - 3])
            win.attroff(cp(PAIR_HEADER) | curses.A_BOLD)
        except curses.error:
            pass

        if album:
            tracks = album.tracks()
            for i, t in enumerate(tracks[:h - 2]):
                is_cur = i == self.track_cursor and self.focus == "tracks"
                line = f"  {t.display_name()}"
                trw = w - half - 3
                if len(line) > trw:
                    line = line[:trw - 1] + "…"
                attr = cp(PAIR_SELECTED) | curses.A_BOLD if is_cur \
                       else cp(PAIR_PLAYING) if self.focus == "tracks" and i == self.track_cursor \
                       else cp(PAIR_DEFAULT)
                try:
                    win.addstr(i + 1, half + 2, line.ljust(trw)[:trw], attr)
                except curses.error:
                    pass

        footer = " ←→ switch | Enter play | [n]ew album | [d]elete | [a]dd track "
        try:
            win.attron(cp(PAIR_MUTED))
            win.addstr(h - 1, 2, footer[:w - 3])
            win.attroff(cp(PAIR_MUTED))
        except curses.error:
            pass

    def handle_key(self, key) -> str | None:
        albums = self._albums()

        if key in (curses.KEY_LEFT, ord("h")):
            self.focus = "albums"
        elif key in (curses.KEY_RIGHT, ord("l")):
            if self._current_album():
                self.focus = "tracks"

        elif key in (curses.KEY_UP, ord("k")):
            if self.focus == "albums":
                self.album_cursor = max(0, self.album_cursor - 1)
                self.track_cursor = 0
            else:
                self.track_cursor = max(0, self.track_cursor - 1)

        elif key in (curses.KEY_DOWN, ord("j")):
            if self.focus == "albums":
                self.album_cursor = min(len(albums) - 1, self.album_cursor + 1)
                self.track_cursor = 0
            else:
                album = self._current_album()
                if album:
                    self.track_cursor = min(len(album.paths) - 1, self.track_cursor + 1)

        elif key in (curses.KEY_ENTER, 10, 13):
            if self.focus == "tracks":
                album = self._current_album()
                if album:
                    tracks = album.tracks()
                    if tracks and self.track_cursor < len(tracks):
                        if self.on_play_album:
                            self.on_play_album(album, self.track_cursor)
                        return "play"
            elif self.focus == "albums":
                album = self._current_album()
                if album and self.on_play_album:
                    self.on_play_album(album, 0)
                    return "play"

        return None

    def refresh(self):
        pass  # library is live-updated
