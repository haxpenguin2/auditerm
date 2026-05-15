"""
Main layout manager.
Divides the terminal into: title bar, main area (browser/library/split), visualizer, controls.
"""

import curses
import threading
import time
from pathlib import Path

from auditerm.config import Config
from auditerm.player import Player, Track
from auditerm.library import Library
from auditerm.ui.colors import (
    init_colors, cp,
    PAIR_ACCENT, PAIR_HEADER, PAIR_MUTED, PAIR_DEFAULT,
    PAIR_TITLE, PAIR_STATUS, PAIR_BORDER, PAIR_PLAYING
)
from auditerm.ui.controls import ControlsBar
from auditerm.ui.browser import FileBrowser, AUDIO_EXTS
from auditerm.ui.library import LibraryPanel
from auditerm.ui.visualizer import Visualizer

ASCII_LOGO = [
    " █████╗ ██╗   ██╗██████╗ ██╗████████╗███████╗██████╗ ███╗   ███╗",
    "██╔══██╗██║   ██║██╔══██╗██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║",
    "███████║██║   ██║██║  ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║",
    "██╔══██║██║   ██║██║  ██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║",
    "██║  ██║╚██████╔╝██████╔╝██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║",
    "╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
]

SMALL_LOGO = ["▌█ AUDITERM █▐"]


class Layout:
    PANEL_SPLIT   = "split"
    PANEL_BROWSER = "browser"
    PANEL_LIBRARY = "library"

    def __init__(self, stdscr, player: Player, library: Library, cfg: Config):
        self.stdscr  = stdscr
        self.player  = player
        self.library = library
        self.cfg     = cfg

        self.panel = cfg.get("ui", "default_panel", "split")
        self.focus = "browser"   # "browser" | "library"

        self.browser   = FileBrowser(cfg)
        self.lib_panel = LibraryPanel(library, cfg)
        self.controls  = ControlsBar(player, cfg)
        self.visualizer = Visualizer(player, cfg)

        self._setup_callbacks()
        self._status_msg = ""
        self._status_expire = 0.0
        self._dialog: str | None = None  # modal text input
        self._dialog_buf = ""
        self._dialog_cb = None

        self._fps = cfg.getint("visualizer", "fps", 20)
        self._running = True

        # windows (created in resize)
        self._wins = {}

    def _setup_callbacks(self):
        def play_file(path: str):
            t = Track(path)
            # build queue from same directory
            parent = Path(path).parent
            siblings = sorted(
                [str(p) for p in parent.iterdir() if p.suffix.lower() in AUDIO_EXTS],
                key=lambda x: x.lower()
            )
            tracks = [Track(p) for p in siblings]
            idx = next((i for i, tr in enumerate(tracks) if tr.path == path), 0)
            self.player.set_queue(tracks, idx)
            self.player.play(Track(path))
            self.status(f"▶  {Track(path).display_name()}")

        def play_album(album, start_idx=0):
            tracks = album.tracks()
            if not tracks:
                self.status("Album is empty.")
                return
            self.player.set_queue(tracks, start_idx)
            self.player.play(tracks[start_idx])
            self.status(f"▶  {album.name}")

        self.browser.on_play = play_file
        self.lib_panel.on_play = play_file
        self.lib_panel.on_play_album = play_album

        self.player.on_track_end(self._on_track_end)

    def _on_track_end(self):
        self.player.next_track()

    def status(self, msg: str, duration: float = 3.0):
        self._status_msg = msg
        self._status_expire = time.time() + duration

    def _make_windows(self):
        h, w = self.stdscr.getmaxyx()
        curses.curs_set(0)

        vis_style = self.cfg.get("visualizer", "style", "bars")
        vis_h = self.cfg.getint("visualizer", "height", 8) if vis_style != "off" else 0
        ctrl_h = 5
        logo_lines = len(ASCII_LOGO) if w >= 70 else len(SMALL_LOGO)
        title_h = logo_lines + 1 if self.cfg.getbool("ui", "title_art", True) else 1

        main_h = h - title_h - vis_h - ctrl_h
        if main_h < 3:
            main_h = 3

        top = 0
        # title
        self._wins["title"] = curses.newwin(title_h, w, top, 0)
        top += title_h
        # main area
        if self.panel == self.PANEL_SPLIT:
            half = w // 2
            self._wins["browser"] = curses.newwin(main_h, half, top, 0)
            self._wins["library"] = curses.newwin(main_h, w - half, top, half)
        elif self.panel == self.PANEL_BROWSER:
            self._wins["browser"] = curses.newwin(main_h, w, top, 0)
            self._wins.pop("library", None)
        elif self.panel == self.PANEL_LIBRARY:
            self._wins["library"] = curses.newwin(main_h, w, top, 0)
            self._wins.pop("browser", None)
        top += main_h
        # visualizer
        if vis_h > 0:
            self._wins["visualizer"] = curses.newwin(vis_h, w, top, 0)
            top += vis_h
        else:
            self._wins.pop("visualizer", None)
        # controls
        self._wins["controls"] = curses.newwin(ctrl_h, w, top, 0)

    def _draw_title(self, win):
        win.erase()
        h, w = win.getmaxyx()
        logo = ASCII_LOGO if w >= 70 else SMALL_LOGO
        try:
            for i, line in enumerate(logo):
                x = max(0, (w - len(line)) // 2)
                win.addstr(i, x, line[:w], cp(PAIR_TITLE) | curses.A_BOLD)
            # status / now playing under logo
            status_row = len(logo)
            if time.time() < self._status_expire:
                msg = self._status_msg
            elif self.player.current_track:
                t = self.player.current_track
                icon = "▶" if self.player.is_playing else "⏸" if self.player.is_paused else "■"
                msg = f"{icon}  {t.display_name()}"
            else:
                msg = "No track loaded — press [b] to browse"
            x = max(0, (w - len(msg)) // 2)
            win.addstr(status_row, x, msg[:w], cp(PAIR_STATUS))
        except curses.error:
            pass

    def run(self):
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)

        try:
            init_colors(self.cfg)
        except Exception:
            pass

        self._make_windows()
        last_resize = 0

        while self._running:
            now = time.time()

            # ── input ─────────────────────────────────────────
            key = self.stdscr.getch()
            if key != -1:
                if self._dialog is not None:
                    self._handle_dialog_key(key)
                else:
                    self._handle_key(key)

            # ── resize ────────────────────────────────────────
            if key == curses.KEY_RESIZE:
                self._make_windows()

            # ── draw ──────────────────────────────────────────
            if "title" in self._wins:
                self._draw_title(self._wins["title"])
                self._wins["title"].noutrefresh()

            if "browser" in self._wins:
                focused = (self.focus == "browser") or (self.panel != self.PANEL_SPLIT)
                self.browser.draw(self._wins["browser"])
                self._wins["browser"].noutrefresh()

            if "library" in self._wins:
                self.lib_panel.draw(self._wins["library"])
                self._wins["library"].noutrefresh()

            if "visualizer" in self._wins:
                self.visualizer.draw(self._wins["visualizer"])
                self._wins["visualizer"].noutrefresh()

            if "controls" in self._wins:
                self.controls.draw(self._wins["controls"])
                self._wins["controls"].noutrefresh()

            # ── dialog overlay ────────────────────────────────
            if self._dialog is not None:
                self._draw_dialog()

            curses.doupdate()
            time.sleep(1.0 / self._fps)

    def _handle_key(self, key):
        p = self.player
        cfg = self.cfg

        # global binds
        quit_key = cfg.get("keybinds", "quit", "q")
        if key == ord(quit_key):
            p.stop()
            self._running = False
            return

        if key == ord(" "):
            p.pause()
            return

        if key == ord("s"):
            p.stop()
            return

        if key == ord(">") or key == curses.KEY_RIGHT and self.panel == self.PANEL_LIBRARY:
            if self.panel != self.PANEL_LIBRARY:
                p.next_track()
            return

        if key == ord("<"):
            p.prev_track()
            return

        if key == ord("+") or key == ord("="):
            p.volume_up()
            return

        if key == ord("-"):
            p.volume_down()
            return

        # panel switching
        if key == ord("b"):
            if self.panel == self.PANEL_BROWSER:
                self.panel = self.PANEL_SPLIT
            else:
                self.panel = self.PANEL_BROWSER
            self._make_windows()
            return

        if key == ord("l"):
            if self.panel == self.PANEL_LIBRARY:
                self.panel = self.PANEL_SPLIT
            else:
                self.panel = self.PANEL_LIBRARY
            self._make_windows()
            return

        if key == 9:  # Tab
            if self.panel == self.PANEL_SPLIT:
                self.focus = "library" if self.focus == "browser" else "browser"
            return

        if key == ord("v"):
            styles = ["bars", "wave", "spectrum", "dots", "off"]
            cur = self.cfg.get("visualizer", "style", "bars")
            nxt = styles[(styles.index(cur) + 1) % len(styles)] if cur in styles else "bars"
            self.cfg._parser.set("visualizer", "style", nxt)
            self._make_windows()
            self.status(f"Visualizer: {nxt}")
            return

        # new album
        if key == ord("n"):
            self._open_dialog("New album name:", self._create_album)
            return

        # add to album
        if key == ord("a"):
            path = self.browser.current_path()
            if path and path.is_file() and path.suffix.lower() in AUDIO_EXTS:
                if self.library.album_names():
                    self._open_dialog(f"Add to album (name):", lambda name: self._add_to_album(name, str(path)))
                else:
                    self.status("No albums yet — press [n] to create one first.")
            return

        # delegate to focused panel
        if self.panel == self.PANEL_SPLIT:
            if self.focus == "browser":
                self.browser.handle_key(key)
            else:
                self.lib_panel.handle_key(key)
        elif self.panel == self.PANEL_BROWSER:
            self.browser.handle_key(key)
        elif self.panel == self.PANEL_LIBRARY:
            result = self.lib_panel.handle_key(key)
            if key == ord(">"):
                self.player.next_track()

    # ── modal dialog ──────────────────────────────────────────────

    def _open_dialog(self, prompt: str, cb):
        self._dialog = prompt
        self._dialog_buf = ""
        self._dialog_cb = cb

    def _handle_dialog_key(self, key):
        if key in (curses.KEY_ENTER, 10, 13):
            val = self._dialog_buf.strip()
            self._dialog = None
            if val and self._dialog_cb:
                self._dialog_cb(val)
        elif key in (27,):  # ESC
            self._dialog = None
        elif key in (curses.KEY_BACKSPACE, 127):
            self._dialog_buf = self._dialog_buf[:-1]
        elif 32 <= key <= 126:
            self._dialog_buf += chr(key)

    def _draw_dialog(self):
        h, w = self.stdscr.getmaxyx()
        dw, dh = 50, 5
        dy = h // 2 - dh // 2
        dx = w // 2 - dw // 2
        try:
            win = curses.newwin(dh, dw, dy, dx)
            win.attron(cp(PAIR_HEADER))
            win.border()
            win.attroff(cp(PAIR_HEADER))
            win.addstr(1, 2, (self._dialog or "")[:dw - 4], cp(PAIR_ACCENT) | curses.A_BOLD)
            buf_display = self._dialog_buf[-dw + 6:]
            win.addstr(3, 2, f"> {buf_display}_"[:dw - 3], cp(PAIR_DEFAULT))
            win.noutrefresh()
        except curses.error:
            pass

    def _create_album(self, name: str):
        self.library.new_album(name)
        self.status(f"Album '{name}' created.")

    def _add_to_album(self, album_name: str, path: str):
        self.library.add_to_album(album_name, path)
        self.status(f"Added to '{album_name}'.")
